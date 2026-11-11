"""v3: velocity-targeted kicks, pruned exact evaluator, bisector keeper,
chaser hysteresis, restart timing."""

import math
import time

from soccer import PlayerAction, TeamAction, TeamController

DT = 0.05
F = 0.985
VMAX = 8.0
ACC = 20.0
KICK = 22.0
BALL_CAP = 30.0
KR = 2.2
XL = 50.0
YL = 30.0
GH = 7.0
BR = 0.45
XM = XL - BR
YM = YL - BR
WALL_E = 0.75
HORIZON = 80
ROLL = DT / (1 - F)          # distance to rest per unit of speed (3.333)

TS = list(range(1, 16)) + list(range(17, 41, 2)) + list(range(43, HORIZON + 1, 3))
NTS = len(TS)
G = [DT * (1 - F ** t) / (1 - F) for t in range(HORIZON + 2)]
GTS = [G[t] for t in TS]
FTS = [F ** t for t in TS]

P = {
    "react": 1.0,          # ticks of opponent reaction we assume
    "r_get": 1.9,          # distance at which a player 'has' the ball
    "sig_keep": 2.5,
    "keep_bias": 1.5,
    "sig_goal": 2.0,
    "goal_bias": 0.5,
    "goal_val": 4.0,
    "lose_base": 0.3,
    "lose_scale": 1.3,
    "pos_prog": 0.35,
    "pos_goal": 0.9,
    "goal_len": 14.0,
    "hyst": 2.0,
    "budget": 1.0,
    "keeper": "bisector",
    "exact": 0,
    "form": 0,
}


def clampf(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ball_path(px, py, vx, vy, n):
    pts = []
    for t in range(1, n + 1):
        px += vx * DT
        py += vy * DT
        vx *= F
        vy *= F
        if py > YM:
            py = 2 * YM - py
            vy = -vy * WALL_E
        elif py < -YM:
            py = -2 * YM - py
            vy = -vy * WALL_E
        if px > XM:
            if abs(py) < GH:
                if px >= XL:
                    pts.append((px, py))
                    return pts, t, 1
            else:
                px = 2 * XM - px
                vx = -vx * WALL_E
        elif px < -XM:
            if abs(py) < GH:
                if px <= -XL:
                    pts.append((px, py))
                    return pts, t, -1
            else:
                px = -2 * XM - px
                vx = -vx * WALL_E
        pts.append((px, py))
        if vx * vx + vy * vy < 0.04:
            break
    return pts, None, 0


def fast_path(bx, by, vx, vy):
    """Sampled path at ticks TS (folded walls). Returns xs, ys, n, gt, gs."""
    xs = []
    ys = []
    for i in range(NTS):
        g = GTS[i]
        x = bx + vx * g
        y = by + vy * g
        if y > YM:
            y = YM - (y - YM) * WALL_E
            if y < -YM:
                y = -YM
        elif y < -YM:
            y = -YM - (y + YM) * WALL_E
            if y > YM:
                y = YM
        if x > XM:
            if abs(y) < GH:
                if x >= XL:
                    xs.append(x)
                    ys.append(y)
                    return xs, ys, len(xs), TS[i], 1
            else:
                x = XM - (x - XM) * WALL_E
        elif x < -XM:
            if abs(y) < GH:
                if x <= -XL:
                    xs.append(x)
                    ys.append(y)
                    return xs, ys, len(xs), TS[i], -1
            else:
                x = -XM - (x + XM) * WALL_E
        xs.append(x)
        ys.append(y)
    return xs, ys, NTS, None, 0


def reach_ticks(px, py, vx, vy, tx, ty, r):
    dx = tx - px
    dy = ty - py
    d = math.sqrt(dx * dx + dy * dy)
    if d <= r:
        return 0.0
    vp = (vx * dx + vy * dy) / d
    dist = d - r
    if vp < -VMAX:
        vp = -VMAX
    ta = (VMAX - vp) / ACC
    da = (VMAX + vp) * 0.5 * ta
    if da >= dist:
        t = (-vp + math.sqrt(max(vp * vp + 2 * ACC * dist, 0.0))) / ACC
    else:
        t = ta + (dist - da) / VMAX
    return t * 20.0


class Body:
    __slots__ = ("id", "x", "y", "vx", "vy", "cd", "team")

    def __init__(self, p, team):
        self.id = p.id
        self.x, self.y = p.position
        self.vx, self.vy = p.velocity
        self.cd = p.kick_cooldown_ticks
        self.team = team


def first_intercept(body, pts, r, start=0):
    n = len(pts)
    x, y, vx, vy = body.x, body.y, body.vx, body.vy
    i = start
    while i < n:
        bx, by = pts[i]
        t = reach_ticks(x, y, vx, vy, bx, by, r)
        if t <= i + 1:
            return i + 1, bx, by
        gap = int(t - (i + 1))
        i += 1 if gap < 2 else min(gap // 2, 6)
    if pts:
        bx, by = pts[-1]
        t = reach_ticks(x, y, vx, vy, bx, by, r)
        return max(t, n), bx, by
    return None, None, None


def first_intercept_lim(body, pts, r, start=0, limit=None):
    n = len(pts)
    if limit is not None and limit < n:
        n = limit
    x, y, vx, vy = body.x, body.y, body.vx, body.vy
    i = start
    while i < n:
        bx, by = pts[i]
        t = reach_ticks(x, y, vx, vy, bx, by, r)
        if t <= i + 1:
            return i + 1, bx, by
        gap = int(t - (i + 1))
        i += 1 if gap < 2 else min(gap // 2, 6)
    if pts and (limit is None or limit >= len(pts)):
        bx, by = pts[-1]
        t = reach_ticks(x, y, vx, vy, bx, by, r)
        return max(t, len(pts)), bx, by
    return None, None, None


def earliest(b, xs, ys, n, r, start, stop_t, delay, sb):
    """First sampled tick in [start, stop_t) when body b reaches the path."""
    x, y, vx, vy = b.x, b.y, b.vx, b.vy
    close = sb * DT + VMAX * DT
    j = 0
    while j < n:
        t = TS[j]
        if t >= stop_t:
            return None, -1
        if t < start:
            j += 1
            continue
        rt = reach_ticks(x, y, vx, vy, xs[j], ys[j], r) + delay
        if rt <= t:
            return t, j
        # Gap in distance can close at most `close` per tick.
        need = t + (rt - t) * VMAX * DT / close
        j += 1
        while j < n and TS[j] < need:
            j += 1
    return None, -1


class MyTeam(TeamController):
    name = "v3"
    version = "3"

    def __init__(self):
        self.p = dict(P)
        self.dead_since = None
        self.chaser_id = None

    def initial_formation(self, field):
        if self.p["form"] == 1:
            return [(-48.0, 0.0), (-28.0, -10.0), (-28.0, 10.0), (-9.5, -1.5), (-14.0, 12.0)]
        return [
            (-48.5, 0.0),
            (-30.0, -9.0),
            (-30.0, 9.0),
            (-9.6, -0.8),
            (-12.0, 14.0),
        ]

    def reset(self, seed):
        self.dead_since = None
        self.chaser_id = None

    # ------------------------------------------------------------------
    def act(self, obs):
        ball = obs.ball
        bx, by = ball.position
        bvx, bvy = ball.velocity
        mine = [Body(p, 0) for p in obs.my_players]
        theirs = [Body(p, 1) for p in obs.opponents]
        actions = TeamAction()

        dead = (bx == 0.0 and by == 0.0 and bvx == 0.0 and bvy == 0.0)
        if dead:
            if self.dead_since is None:
                self.dead_since = obs.tick
        else:
            self.dead_since = None
        their_kickoff = (dead and ball.controlling_team == 1
                         and obs.tick - self.dead_since < 62)

        pts, gtick, gside = ball_path(bx, by, bvx, bvy, HORIZON)
        if not pts:
            pts = [(bx, by)]

        r = self.p["r_get"]
        my_ic = {b.id: first_intercept(b, pts, r) for b in mine}
        opp_best = 1e9
        opp_best_body = None
        for b in theirs:
            t, _, _ = first_intercept(b, pts, r)
            if t is not None and t < opp_best:
                opp_best = t
                opp_best_body = b

        field_players = mine[1:]
        chaser = None
        best = 1e9
        for b in field_players:
            t = my_ic[b.id][0]
            if t is None:
                continue
            if b.id == self.chaser_id:
                t -= self.p["hyst"]
            if t < best:
                best = t
                chaser = b
        keeper = mine[0]
        kt, kx, ky = my_ic[0]
        if kt is not None and kx is not None and kt < best and kx < -38 and abs(ky) < 16:
            chaser = keeper
            best = kt
        self.chaser_id = chaser.id if chaser is not None else None
        we_first = best < opp_best

        used = set()
        if not their_kickoff:
            for b in sorted(mine, key=lambda q: (q.x - bx) ** 2 + (q.y - by) ** 2):
                if obs.can_kick(b.id):
                    actions.set(b.id, self.choose_kick(b, mine, theirs, bx, by, bvx, bvy))
                    used.add(b.id)
                    break

        if chaser is not None and chaser.id not in used and not their_kickoff:
            _, ix, iy = my_ic[chaser.id]
            if ix is None:
                ix, iy = bx, by
            tx, ty = self.approach_point(chaser, ix, iy)
            actions.set(chaser.id, PlayerAction(movement=self.toward(chaser, tx, ty, 0.3)))
            used.add(chaser.id)

        if 0 not in used:
            actions.set(0, PlayerAction(movement=self.keeper_move(keeper, bx, by, pts, gtick, gside)))
            used.add(0)

        rest = [b for b in field_players if b.id not in used]
        spots = self.shape_spots(we_first, bx, by, theirs, len(rest), opp_best_body)
        for b, (tx, ty) in self.assign(rest, spots):
            if their_kickoff:
                tx, ty = self.outside_circle(tx, ty)
            actions.set(b.id, PlayerAction(movement=self.toward(b, tx, ty)))
        if their_kickoff:
            for pid, a in list(actions.players.items()):
                b = mine[pid]
                mx, my = a.movement
                nx, ny = b.x + mx * 1.0, b.y + my * 1.0
                if nx * nx + ny * ny < 10.5 ** 2:
                    tx, ty = self.outside_circle(b.x, b.y)
                    actions.set(pid, PlayerAction(movement=self.toward(b, tx, ty)))
        return actions

    # ------------------------------------------------------------------
    @staticmethod
    def outside_circle(x, y, rad=10.5):
        d = math.hypot(x, y)
        if d >= rad:
            return x, y
        if d < 1e-6:
            return -rad, 0.0
        return x / d * rad, y / d * rad

    @staticmethod
    def toward(b, tx, ty, slow_radius=1.5):
        dx = tx - b.x
        dy = ty - b.y
        d = math.hypot(dx, dy)
        if d < 1e-6:
            return (0.0, 0.0)
        s = 1.0 if d > slow_radius else d / slow_radius
        return (dx / d * s, dy / d * s)

    @staticmethod
    def approach_point(b, ix, iy):
        dx, dy = XL - ix, -iy
        d = math.hypot(dx, dy) or 1.0
        if math.hypot(b.x - ix, b.y - iy) > 6:
            return ix, iy
        return ix - dx / d * 0.8, iy - dy / d * 0.8

    def keeper_move(self, k, bx, by, pts, gtick, gside):
        if gside == -1 and gtick is not None:
            best = None
            for i, (px, py) in enumerate(pts):
                t = reach_ticks(k.x, k.y, k.vx, k.vy, px, py, 1.3)
                if t <= i + 1:
                    best = (px, py)
                    break
            if best is None:
                best = pts[-1]
            return self.toward(k, best[0], best[1], 0.3)
        if self.p["keeper"] == "line":
            gx = -XL
            dx, dy = bx - gx, by
            d = math.hypot(dx, dy) or 1.0
            depth = clampf(d * 0.12, 1.5, 4.0)
            tx = gx + dx / d * depth
            ty = clampf(dy / d * depth * 2.0 + by * 0.12, -GH + 1.0, GH - 1.0)
            tx = max(tx, -XL + 1.2)
            return self.toward(k, tx, ty, 1.0)
        # Bisector of the angle the ball sees the two posts at.
        ax, ay = -XL - bx, GH - by
        cx, cy = -XL - bx, -GH - by
        la = math.hypot(ax, ay) or 1.0
        lc = math.hypot(cx, cy) or 1.0
        ux, uy = ax / la + cx / lc, ay / la + cy / lc
        lu = math.hypot(ux, uy) or 1.0
        ux, uy = ux / lu, uy / lu
        dball = math.hypot(bx + XL, by)
        depth = clampf(dball * 0.10, 1.2, 4.5)
        # Walk back from the goal line towards the ball along the bisector.
        if ux < -1e-3:
            s = depth / -ux
        else:
            s = depth
        tx = -XL + depth
        ty = clampf(by + uy * (math.hypot(bx - tx, 0) / max(-ux, 0.2)) * 0 + 0, -GH, GH)
        # Point on the bisector line at x = tx.
        if abs(ux) > 1e-3:
            lam = (tx - bx) / ux
            ty = by + uy * lam
        ty = clampf(ty, -GH + 0.8, GH - 0.8)
        return self.toward(k, tx, ty, 1.0)

    def shape_spots(self, attacking, bx, by, theirs, n, presser):
        spots = []
        if attacking:
            side = -1.0 if by > 0 else 1.0
            spots.append((clampf(bx + 16, -10, 38), clampf(side * 9, -20, 20)))
            spots.append((clampf(bx + 10, -10, 36), clampf(-side * 14, -24, 24)))
            spots.append((clampf(bx - 8, -35, 20), clampf(by + side * 12, -24, 24)))
            spots.append((clampf(bx - 30, -36, 0), clampf(by * 0.3, -10, 10)))
        else:
            dx, dy = -XL - bx, -by
            d = math.hypot(dx, dy) or 1.0
            spots.append((bx + dx / d * min(8.0, d * 0.4), by + dy / d * min(8.0, d * 0.4)))
            danger = sorted(theirs, key=lambda o: math.hypot(o.x + XL, o.y))
            for o in danger:
                if presser is not None and o.id == presser.id:
                    continue
                ddx, ddy = -XL - o.x, -o.y
                dd = math.hypot(ddx, ddy) or 1.0
                spots.append((o.x + ddx / dd * 2.5, o.y + ddy / dd * 2.5))
            spots.append((-38.0, 0.0))
        return spots[:max(n, 0)] if n <= len(spots) else spots

    @staticmethod
    def assign(bodies, spots):
        out = []
        free = list(bodies)
        for sx, sy in spots:
            if not free:
                break
            b = min(free, key=lambda q: (q.x - sx) ** 2 + (q.y - sy) ** 2)
            free.remove(b)
            out.append((b, (sx, sy)))
        for b in free:
            out.append((b, (b.x, b.y)))
        return out

    # ------------------------------------------------------------------
    def pos_value(self, x, y):
        p = self.p
        dg = math.hypot(XL - x, y)
        return p["pos_prog"] * (x / XL) + p["pos_goal"] * math.exp(-dg / p["goal_len"])

    def lose_value(self, x, y):
        p = self.p
        dg = math.hypot(-XL - x, y)
        return -p["lose_base"] - p["lose_scale"] * math.exp(-dg / p["goal_len"])

    def evaluate_exact(self, kicker, mine, theirs, bx, by, vx, vy):
        p = self.p
        pts, gt, gs = ball_path(bx, by, vx, vy, HORIZON)
        if not pts:
            return -9.0
        r = p["r_get"]
        horizon = gt if gt is not None else None
        ot = 1e9
        opx = opy = None
        for o in theirs:
            t, px, py = first_intercept_lim(o, pts, r, 0, horizon)
            if t is not None and t < ot:
                ot, opx, opy = t, px, py
        mt = 1e9
        mpx = mpy = None
        for m in mine:
            t, px, py = first_intercept_lim(m, pts, r, 5 if m.id == kicker.id else 0, horizon)
            if t is not None and t < mt:
                mt, mpx, mpy = t, px, py
        if gs == 1:
            margin = ot - gt
            q = 1.0 / (1.0 + math.exp(-(margin - p["goal_bias"]) / p["sig_goal"]))
            return q * p["goal_val"] + (1 - q) * (-0.4)
        if gs == -1:
            return -10.0
        if mt < ot:
            margin = ot - mt
            q = 1.0 / (1.0 + math.exp(-(margin - p["keep_bias"]) / p["sig_keep"]))
            return q * self.pos_value(mpx, mpy) + (1 - q) * self.lose_value(mpx, mpy)
        if opx is None:
            return -1.0
        return self.lose_value(opx, opy)

    def evaluate(self, kicker, mine, theirs, bx, by, vx, vy):
        p = self.p
        if p["exact"]:
            return self.evaluate_exact(kicker, mine, theirs, bx, by, vx, vy)
        sb = math.hypot(vx, vy)
        xs, ys, n, gt, gs = fast_path(bx, by, vx, vy)
        if n == 0:
            return -9.0
        stop = gt + 1 if gt is not None else 10 ** 6
        r = p["r_get"]
        ot = stop
        oj = -1
        for o in theirs:
            t, j = earliest(o, xs, ys, n, r, 0, ot, p["react"], sb)
            if t is not None:
                ot, oj = t, j
        mt = ot
        mj = -1
        for m in mine:
            t, j = earliest(m, xs, ys, n, r, 5 if m.id == kicker.id else 0, mt, 0.0, sb)
            if t is not None:
                mt, mj = t, j
        if gs == 1:
            if oj < 0:
                return p["goal_val"]
            margin = ot - gt
            q = 1.0 / (1.0 + math.exp(-(margin - p["goal_bias"]) / p["sig_goal"]))
            return q * p["goal_val"] + (1 - q) * (-0.4)
        if gs == -1 and oj < 0 and mj < 0:
            return -10.0
        if mj >= 0:
            margin = (ot if oj >= 0 else mt + 30) - mt
            q = 1.0 / (1.0 + math.exp(-(margin - p["keep_bias"]) / p["sig_keep"]))
            px, py = xs[mj], ys[mj]
            return q * self.pos_value(px, py) + (1 - q) * self.lose_value(px, py)
        if oj >= 0:
            return self.lose_value(xs[oj], ys[oj])
        px, py = xs[n - 1], ys[n - 1]
        return 0.5 * self.pos_value(px, py) + 0.5 * self.lose_value(px, py)

    @staticmethod
    def kick_for(bvx, bvy, ux, uy, speed):
        """Kick (dir, power) giving the ball velocity speed*u, or the fastest
        achievable along u when speed is unreachable. None if u is unreachable."""
        dvx = ux * speed - bvx
        dvy = uy * speed - bvy
        dv = math.hypot(dvx, dvy)
        if dv <= KICK:
            if dv < 1e-6:
                return None
            return dvx / dv, dvy / dv, dv / KICK, speed
        # Fastest speed along u reachable with |dv| <= KICK.
        ub = ux * bvx + uy * bvy
        disc = KICK * KICK - (bvx * bvx + bvy * bvy) + ub * ub
        if disc < 0:
            return None
        s = ub + math.sqrt(disc)
        if s <= 0.5:
            return None
        s = min(s, BALL_CAP)
        dvx = ux * s - bvx
        dvy = uy * s - bvy
        dv = math.hypot(dvx, dvy)
        if dv < 1e-6:
            return None
        return dvx / dv, dvy / dv, min(dv / KICK, 1.0), s

    def choose_kick(self, k, mine, theirs, bx, by, bvx, bvy):
        targets = []   # (ux, uy, speed)
        for gy in (-6.0, -4.5, -3.0, -1.5, 0.0, 1.5, 3.0, 4.5, 6.0):
            dx, dy = XL - bx, gy - by
            d = math.hypot(dx, dy)
            targets.append((dx / d, dy / d, BALL_CAP))
        for m in mine:
            if m.id == k.id:
                continue
            for lead in (0.0, 0.5, 1.0):
                tx = m.x + m.vx * lead
                ty = m.y + m.vy * lead
                dx, dy = tx - bx, ty - by
                d = math.hypot(dx, dy)
                if d < 3:
                    continue
                for vend in (5.0, 10.0):
                    targets.append((dx / d, dy / d, vend + d / ROLL))
        for i in range(16):
            a = i * math.pi / 8
            c, s = math.cos(a), math.sin(a)
            for sp in (7.0, 11.0):
                targets.append((c, s, sp))
        for i in range(16):
            a = i * math.pi / 8
            targets.append((math.cos(a), math.sin(a), BALL_CAP))
        best = None
        bestv = -1e9
        deadline = time.perf_counter() + self.p["budget"]
        for i, (ux, uy, sp) in enumerate(targets):
            if (i & 7) == 7 and time.perf_counter() > deadline:
                break
            kk = self.kick_for(bvx, bvy, ux, uy, sp)
            if kk is None:
                continue
            kx, ky, pw, s = kk
            v = self.evaluate(k, mine, theirs, bx, by, ux * s, uy * s)
            if v > bestv:
                bestv = v
                best = (kx, ky, pw, ux, uy)
        if best is None:
            return PlayerAction(movement=(1.0, 0.0), kick_direction=(1.0, 0.0), kick_power=1.0)
        kx, ky, pw, ux, uy = best
        return PlayerAction(movement=(ux, uy), kick_direction=(kx, ky), kick_power=pw)
