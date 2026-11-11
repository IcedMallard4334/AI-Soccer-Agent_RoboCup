"""v5: v4 + keeper positioned to maximise its worst-case corner-save margin."""

import math

from soccer import PlayerAction, TeamAction, TeamController

DT = 0.05
F = 0.985
VMAX = 8.0
ACC = 20.0
KICK = 22.0
BALL_CAP = 30.0
XL = 50.0
YL = 30.0
GH = 7.0
BR = 0.45
XM = XL - BR
YM = YL - BR
WALL_E = 0.75
HORIZON = 80
ROLL = DT / (1 - F)

P = {
    "react": 0.0,
    "r_get": 1.9,
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
    # support positioning
    "sup_every": 3,
    "sup_v": 1.0,
    "sup_lane": 0.12,
    "sup_open": 0.05,
    "sup_dist": 0.02,
    "rear_depth": 22.0,
    # defence
    "cover_dist": 7.0,
    "mark_goal_side": 2.0,
    "mark_ball_frac": 0.25,
    # keeper
    "gk_speed": 28.0,
    "gk_r": 1.9,
    "gk_max": 12.0,
    "gk_mode": 1,
}

LNF = math.log(F)


def ball_ticks(dist, speed):
    """Ticks for a ball struck at `speed` to roll `dist`; 999 if it never does."""
    q = 1.0 - dist / (ROLL * speed)
    if q <= 0.0:
        return 999.0
    return math.log(q) / LNF


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
    __slots__ = ("id", "x", "y", "vx", "vy", "cd")

    def __init__(self, p):
        self.id = p.id
        self.x, self.y = p.position
        self.vx, self.vy = p.velocity
        self.cd = p.kick_cooldown_ticks


def first_intercept(body, pts, r, start=0, limit=None, delay=0.0):
    """Earliest tick (1-based) at which body can be within r of the path,
    considering only ticks < limit. Returns (t, x, y) or (None, None, None)."""
    n = len(pts)
    capped = limit is not None and limit <= n
    if capped:
        n = int(limit) - 1
        if n < 0:
            n = 0
    x, y, vx, vy = body.x, body.y, body.vx, body.vy
    i = start
    while i < n:
        bx, by = pts[i]
        t = reach_ticks(x, y, vx, vy, bx, by, r) + delay
        if t <= i + 1:
            return i + 1, bx, by
        gap = int(t - (i + 1))
        i += 1 if gap < 2 else min(gap // 2, 6)
    if pts and not capped:
        bx, by = pts[-1]
        t = reach_ticks(x, y, vx, vy, bx, by, r) + delay
        t = max(t, len(pts))
        if limit is None or t < limit:
            return t, bx, by
    return None, None, None


class MyTeam(TeamController):
    name = "v5"
    version = "5"

    def __init__(self):
        self.p = dict(P)
        self.dead_since = None
        self.chaser_id = None
        self.sup_cache = None
        self.sup_tick = -100

    def initial_formation(self, field):
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
        self.sup_cache = None
        self.sup_tick = -100

    # ------------------------------------------------------------------
    def act(self, obs):
        p = self.p
        ball = obs.ball
        bx, by = ball.position
        bvx, bvy = ball.velocity
        mine = [Body(q) for q in obs.my_players]
        theirs = [Body(q) for q in obs.opponents]
        actions = TeamAction()
        tick = obs.tick

        dead = (bx == 0.0 and by == 0.0 and bvx == 0.0 and bvy == 0.0)
        if dead:
            if self.dead_since is None:
                self.dead_since = tick
        else:
            self.dead_since = None
        their_kickoff = (dead and ball.controlling_team == 1
                         and tick - self.dead_since < 62)

        pts, gtick, gside = ball_path(bx, by, bvx, bvy, HORIZON)
        if not pts:
            pts = [(bx, by)]

        r = p["r_get"]
        my_ic = {b.id: first_intercept(b, pts, r) for b in mine}
        opp_ic = {b.id: first_intercept(b, pts, r) for b in theirs}
        opp_best = 1e9
        opp_first = None
        for b in theirs:
            t = opp_ic[b.id][0]
            if t is not None and t < opp_best:
                opp_best = t
                opp_first = b

        field_players = mine[1:]
        chaser = None
        best = 1e9
        for b in field_players:
            t = my_ic[b.id][0]
            if t is None:
                continue
            if b.id == self.chaser_id:
                t -= p["hyst"]
            if t < best:
                best = t
                chaser = b
        keeper = mine[0]
        kt, kx, ky = my_ic[0]
        if kt is not None and kx is not None and kt < best and kx < -38 and abs(ky) < 16:
            chaser = keeper
            best = kt
        self.chaser_id = chaser.id if chaser is not None else None
        attacking = best < opp_best

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

        if not attacking and opp_first is not None and opp_ic[opp_first.id][1] is not None:
            self.threat = (opp_ic[opp_first.id][1], opp_ic[opp_first.id][2])
        else:
            self.threat = (bx, by)
        if 0 not in used:
            actions.set(0, PlayerAction(movement=self.keeper_move(keeper, bx, by, pts, gtick, gside)))
            used.add(0)

        rest = [b for b in field_players if b.id not in used]
        if attacking:
            # Where the ball will be when we get it.
            if chaser is not None and my_ic[chaser.id][1] is not None:
                hx, hy = my_ic[chaser.id][1], my_ic[chaser.id][2]
            else:
                hx, hy = bx, by
            plan = self.support_plan(rest, theirs, hx, hy, tick)
        else:
            plan = self.defence_plan(rest, theirs, bx, by, opp_first, opp_ic)
        for b, (tx, ty) in plan:
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

    def keeper_spot(self, tx, ty):
        """Keeper spot on the bisector maximising the worst corner margin
        against a shot struck from (tx, ty)."""
        p = self.p
        ax, ay = -XL - tx, GH - ty
        cx, cy = -XL - tx, -GH - ty
        la = math.hypot(ax, ay) or 1.0
        lc = math.hypot(cx, cy) or 1.0
        ux, uy = ax / la + cx / lc, ay / la + cy / lc
        lu = math.hypot(ux, uy) or 1.0
        ux, uy = ux / lu, uy / lu
        # Points on the bisector measured from the shooter; the goal mouth
        # crossing of the bisector is at distance dg.
        if ux < -1e-3:
            dg = (-XL - tx) / ux
        else:
            dg = math.hypot(-XL - tx, -ty)
        sp = p["gk_speed"]
        targets = ((-XL, GH - 0.6), (-XL, -GH + 0.6))
        best = None
        bestm = -1e9
        s = 0.8
        while s <= p["gk_max"]:
            dist_from_shooter = dg - s
            if dist_from_shooter < 2.0:
                break
            kx = tx + ux * dist_from_shooter
            ky = ty + uy * dist_from_shooter
            if kx < -XL + 0.8:
                s += 0.8
                continue
            m = 1e9
            for gx, gy in targets:
                lx, ly = gx - tx, gy - ty
                ll = math.hypot(lx, ly) or 1.0
                lx /= ll
                ly /= ll
                along = (kx - tx) * lx + (ky - ty) * ly
                h = abs((kx - tx) * ly - (ky - ty) * lx)
                tb = ball_ticks(max(along, 0.0), sp)
                tk = reach_ticks(0.0, 0.0, 0.0, 0.0, h, 0.0, p["gk_r"]) + 1.0
                mm = tb - tk
                if mm < m:
                    m = mm
            if m > bestm:
                bestm = m
                best = (kx, ky)
            s += 0.8
        if best is None:
            return -XL + 1.0, clampf(ty, -GH + 1.0, GH - 1.0)
        return best

    def keeper_move(self, k, bx, by, pts, gtick, gside):
        if self.p["gk_mode"] == 0:
            return self.keeper_move_old(k, bx, by, pts, gtick, gside)
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
        tx, ty = self.threat
        kx, ky = self.keeper_spot(tx, ty)
        return self.toward(k, kx, ky, 0.8)

    def keeper_move_old(self, k, bx, by, pts, gtick, gside):
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
        gx = -XL
        dx, dy = bx - gx, by
        d = math.hypot(dx, dy) or 1.0
        depth = clampf(d * 0.12, 1.5, 4.0)
        tx = gx + dx / d * depth
        ty = clampf(dy / d * depth * 2.0 + by * 0.12, -GH + 1.0, GH - 1.0)
        tx = max(tx, -XL + 1.2)
        return self.toward(k, tx, ty, 1.0)

    # ------------------------------------------------------------------
    def support_plan(self, bodies, theirs, hx, hy, tick):
        """Attacking shape: one rear guard, the rest on the best open spots."""
        p = self.p
        out = []
        free = list(bodies)
        if not free:
            return out
        # Rear guard: the deepest player stays behind the ball.
        rx = clampf(min(hx - p["rear_depth"], 5.0), -38.0, 10.0)
        ry = clampf(hy * 0.3, -12.0, 12.0)
        if len(free) >= 3:
            g = min(free, key=lambda q: (q.x - rx) ** 2 + (q.y - ry) ** 2)
            free.remove(g)
            out.append((g, (rx, ry)))
        if not free:
            return out
        if self.sup_cache is None or tick - self.sup_tick >= p["sup_every"]:
            self.sup_cache = self.score_spots(theirs, hx, hy)
            self.sup_tick = tick
        spots = self.sup_cache
        chosen = []
        for b in free:
            bestv = -1e9
            bests = None
            for sv, sx, sy in spots:
                ok = True
                for cx, cy in chosen:
                    if (cx - sx) ** 2 + (cy - sy) ** 2 < 100.0:
                        ok = False
                        break
                if not ok:
                    continue
                v = sv - p["sup_dist"] * math.hypot(b.x - sx, b.y - sy)
                if v > bestv:
                    bestv = v
                    bests = (sx, sy)
            if bests is None:
                bests = (b.x, b.y)
            chosen.append(bests)
            out.append((b, bests))
        return out

    def score_spots(self, theirs, hx, hy):
        p = self.p
        spots = []
        x0 = clampf(hx - 10.0, -40.0, 40.0)
        for ix in range(8):
            sx = x0 + ix * 5.0
            if sx > 46.0:
                break
            for iy in range(9):
                sy = -24.0 + iy * 6.0
                dx, dy = sx - hx, sy - hy
                L = math.hypot(dx, dy)
                if L < 6.0:
                    continue
                ux, uy = dx / L, dy / L
                lane = 10.0
                opn = 10.0
                for o in theirs:
                    ox, oy = o.x - hx, o.y - hy
                    u = ox * ux + oy * uy
                    h = abs(ox * uy - oy * ux)
                    if 0.0 < u < L:
                        m = h - (1.5 + 0.22 * u)
                        if m < lane:
                            lane = m
                    do = math.hypot(o.x - sx, o.y - sy)
                    if do < opn:
                        opn = do
                v = (p["sup_v"] * self.pos_value(sx, sy)
                     + p["sup_lane"] * clampf(lane, -5.0, 5.0)
                     + p["sup_open"] * opn)
                spots.append((v, sx, sy))
        spots.sort(reverse=True)
        return spots[:20]

    def defence_plan(self, bodies, theirs, bx, by, first, opp_ic):
        """Cover the ball's route to goal, then cut lanes to dangerous men."""
        p = self.p
        out = []
        free = list(bodies)
        if not free:
            return out
        # Where they will have the ball.
        if first is not None and opp_ic[first.id][1] is not None:
            hx, hy = opp_ic[first.id][1], opp_ic[first.id][2]
        else:
            hx, hy = bx, by
        targets = []
        dx, dy = -XL - hx, -hy
        d = math.hypot(dx, dy) or 1.0
        cd = min(p["cover_dist"], d * 0.5)
        targets.append((hx + dx / d * cd, hy + dy / d * cd))
        danger = []
        for o in theirs:
            if first is not None and o.id == first.id:
                continue
            dg = math.hypot(o.x + XL, o.y)
            danger.append((dg, o))
        danger.sort(key=lambda t: t[0])
        for dg, o in danger:
            # Goal-side of the man, pulled towards the ball to cut the lane.
            gx, gy = -XL - o.x, -o.y
            gl = math.hypot(gx, gy) or 1.0
            mx = o.x + gx / gl * p["mark_goal_side"]
            my = o.y + gy / gl * p["mark_goal_side"]
            f = p["mark_ball_frac"]
            mx += (hx - mx) * f * 0.5
            my += (hy - my) * f * 0.5
            targets.append((mx, my))
        targets.append((-36.0, 0.0))
        for sx, sy in targets:
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

    def evaluate(self, kicker, mine, theirs, bx, by, vx, vy):
        p = self.p
        pts, gt, gs = ball_path(bx, by, vx, vy, HORIZON)
        if not pts:
            return -9.0
        r = p["r_get"]
        lim = gt + 1 if gt is not None else None
        ot = lim
        opt = None
        for o in theirs:
            t, px, py = first_intercept(o, pts, r, 0, ot, p["react"])
            if t is not None:
                ot, opt = t, (px, py)
        mt = ot
        mpt = None
        for m in mine:
            t, px, py = first_intercept(m, pts, r, 5 if m.id == kicker.id else 0, mt)
            if t is not None:
                mt, mpt = t, (px, py)
        if gs == 1:
            if opt is None:
                return p["goal_val"]
            margin = ot - gt
            q = 1.0 / (1.0 + math.exp(-(margin - p["goal_bias"]) / p["sig_goal"]))
            return q * p["goal_val"] + (1 - q) * (-0.4)
        if gs == -1 and opt is None and mpt is None:
            return -10.0
        if mpt is not None:
            margin = (ot - mt) if opt is not None else 30.0
            q = 1.0 / (1.0 + math.exp(-(margin - p["keep_bias"]) / p["sig_keep"]))
            return q * self.pos_value(*mpt) + (1 - q) * self.lose_value(*mpt)
        if opt is not None:
            return self.lose_value(*opt)
        return -1.0

    @staticmethod
    def kick_for(bvx, bvy, ux, uy, speed):
        dvx = ux * speed - bvx
        dvy = uy * speed - bvy
        dv = math.hypot(dvx, dvy)
        if dv <= KICK:
            if dv < 1e-6:
                return None
            return dvx / dv, dvy / dv, dv / KICK, speed
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
        targets = []
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
            for sp in (6.0, 9.0, 12.0):
                targets.append((c, s, sp))
            targets.append((c, s, BALL_CAP))
        best = None
        bestv = -1e9
        for ux, uy, sp in targets:
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
