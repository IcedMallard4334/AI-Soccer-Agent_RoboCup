"""v2: v1 with a fast closed-form kick evaluator."""

import math

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
HORIZON = 70

# Ticks at which a candidate kick's path is sampled: dense early, sparse later.
TS = list(range(1, 13)) + list(range(14, 41, 2)) + list(range(43, HORIZON + 1, 3))
# Distance factor: ball displacement after t ticks is v0 * G[t].
G = [DT * (1 - F ** t) / (1 - F) for t in range(HORIZON + 2)]
GTS = [G[t] for t in TS]
# How far a player can run in t ticks beyond his coasting point (3 tick lag).
RUN = [max(0.0, VMAX * DT * (t - 3)) for t in range(HORIZON + 2)]
RUNTS = [RUN[t] for t in TS]


def clampf(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ball_path(px, py, vx, vy, n):
    """Exact stepped prediction for ticks 1..n. Returns (points, goal_tick, goal_side)."""
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
    """Sampled path at ticks TS with folded wall bounces.

    Returns (xs, ys, n, goal_tick, goal_side) where n is how many samples are
    valid (the path stops at a goal).
    """
    xs = []
    ys = []
    gt = None
    gs = 0
    for g in GTS:
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
                    gt = TS[len(xs)]
                    gs = 1
                    xs.append(x)
                    ys.append(y)
                    break
            else:
                x = XM - (x - XM) * WALL_E
        elif x < -XM:
            if abs(y) < GH:
                if x <= -XL:
                    gt = TS[len(xs)]
                    gs = -1
                    xs.append(x)
                    ys.append(y)
                    break
            else:
                x = -XM - (x + XM) * WALL_E
        xs.append(x)
        ys.append(y)
    return xs, ys, len(xs), gt, gs


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
    __slots__ = ("id", "x", "y", "vx", "vy", "cd", "team", "cx", "cy")

    def __init__(self, p, team):
        self.id = p.id
        self.x, self.y = p.position
        self.vx, self.vy = p.velocity
        self.cd = p.kick_cooldown_ticks
        self.team = team
        self.cx = self.x + self.vx * 0.15
        self.cy = self.y + self.vy * 0.15


def first_intercept(body, pts, r, start=0, limit=None):
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


def earliest(cx, cy, r, xs, ys, n, start, stop_t):
    """First sampled tick >= start (and < stop_t) at which a runner coasting
    from (cx, cy) can be within r of the ball. Returns (t, index) or (None, -1)."""
    for j in range(n):
        t = TS[j]
        if t < start:
            continue
        if t >= stop_t:
            return None, -1
        rr = r + RUNTS[j]
        dx = xs[j] - cx
        dy = ys[j] - cy
        if dx * dx + dy * dy <= rr * rr:
            return t, j
    return None, -1


class MyTeam(TeamController):
    name = "v2"
    version = "2"

    def initial_formation(self, field):
        return [
            (-48.0, 0.0),
            (-28.0, -10.0),
            (-28.0, 10.0),
            (-9.5, -1.5),
            (-14.0, 12.0),
        ]

    def act(self, obs):
        ball = obs.ball
        bx, by = ball.position
        bvx, bvy = ball.velocity
        mine = [Body(p, 0) for p in obs.my_players]
        theirs = [Body(p, 1) for p in obs.opponents]
        actions = TeamAction()

        dead = (bx == 0.0 and by == 0.0 and bvx == 0.0 and bvy == 0.0)
        their_kickoff = dead and ball.controlling_team == 1

        pts, gtick, gside = ball_path(bx, by, bvx, bvy, HORIZON)
        if not pts:
            pts = [(bx, by)]

        r = KR - 0.35
        my_ic = {}
        for b in mine:
            my_ic[b.id] = first_intercept(b, pts, r)
        opp_best = 1e9
        opp_best_body = None
        for b in theirs:
            t, _, _ = first_intercept(b, pts, r)
            if t is not None and t < opp_best:
                opp_best = t
                opp_best_body = b

        field_players = [b for b in mine if b.id != 0]
        chaser = None
        best = 1e9
        for b in field_players:
            t = my_ic[b.id][0]
            if t is not None and t < best:
                best = t
                chaser = b
        keeper = mine[0]
        kt = my_ic[0][0]
        if kt is not None and kt < best and my_ic[0][1] is not None and my_ic[0][1] < -38 and abs(my_ic[0][2]) < 16:
            chaser = keeper
            best = kt

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
            actions.set(chaser.id, PlayerAction(movement=self.toward(chaser, tx, ty)))
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
        gx, gy = XL, 0.0
        dx, dy = gx - ix, gy - iy
        d = math.hypot(dx, dy) or 1.0
        ox, oy = ix - dx / d * 0.8, iy - dy / d * 0.8
        if math.hypot(b.x - ix, b.y - iy) > 6:
            return ix, iy
        return ox, oy

    def keeper_move(self, k, bx, by, pts, gtick, gside):
        if gside == -1 and gtick is not None:
            best = None
            for i, (px, py) in enumerate(pts):
                if px > -40:
                    continue
                t = reach_ticks(k.x, k.y, k.vx, k.vy, px, py, 1.2)
                if t <= i + 1:
                    best = (px, py)
                    break
            if best is None:
                best = pts[-1]
            return self.toward(k, best[0], best[1], 0.5)
        gx = -XL
        dx, dy = bx - gx, by
        d = math.hypot(dx, dy) or 1.0
        depth = clampf(d * 0.12, 1.5, 4.0)
        tx = gx + dx / d * depth
        ty = clampf(dy / d * depth * 2.0 + by * 0.12, -GH + 1.0, GH - 1.0)
        tx = max(tx, -XL + 1.2)
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
            gx = -XL
            dx, dy = gx - bx, -by
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

    @staticmethod
    def pos_value(x, y):
        dg = math.hypot(XL - x, y)
        return 0.35 * (x / XL) + 0.9 * math.exp(-dg / 14.0)

    @staticmethod
    def lose_value(x, y):
        dg = math.hypot(-XL - x, y)
        return -0.3 - 1.2 * math.exp(-dg / 14.0)

    def evaluate(self, kicker, mine, theirs, bx, by, vx, vy):
        sp = math.hypot(vx, vy)
        if sp > BALL_CAP:
            vx *= BALL_CAP / sp
            vy *= BALL_CAP / sp
        xs, ys, n, gt, gs = fast_path(bx, by, vx, vy)
        if n == 0:
            return -9.0
        stop = gt + 1 if gt is not None else 10 ** 6
        ot = stop
        oj = -1
        r = KR - 0.35
        for o in theirs:
            t, j = earliest(o.cx, o.cy, r, xs, ys, n, 0, ot)
            if t is not None:
                ot, oj = t, j
        mt = ot
        mj = -1
        for m in mine:
            t, j = earliest(m.cx, m.cy, r, xs, ys, n, 5 if m.id == kicker.id else 0, mt)
            if t is not None:
                mt, mj = t, j
        if gs == 1 and oj < 0:
            return 4.0
        if gs == 1:
            margin = ot - gt
            p = 1.0 / (1.0 + math.exp(-(margin - 1.0) / 2.0))
            return p * 4.0 + (1 - p) * (-0.4)
        if gs == -1 and oj < 0 and mj < 0:
            return -10.0
        if mj >= 0:
            margin = (ot if oj >= 0 else mt + 30) - mt
            p = 1.0 / (1.0 + math.exp(-(margin - 2.0) / 2.5))
            px, py = xs[mj], ys[mj]
            return p * self.pos_value(px, py) + (1 - p) * self.lose_value(px, py)
        if oj >= 0:
            return self.lose_value(xs[oj], ys[oj])
        # Nobody reaches it in the horizon: it rolls to rest near the end.
        px, py = xs[n - 1], ys[n - 1]
        return 0.5 * self.pos_value(px, py) + 0.5 * self.lose_value(px, py)

    def choose_kick(self, k, mine, theirs, bx, by, bvx, bvy):
        cands = []
        for gy in (-5.5, -3.5, -1.5, 1.5, 3.5, 5.5):
            dx, dy = XL + 1.0 - bx, gy - by
            d = math.hypot(dx, dy)
            cands.append((dx / d, dy / d, 1.0))
        for m in mine:
            if m.id == k.id:
                continue
            for lead in (0.0, 0.6):
                tx = m.x + m.vx * lead
                ty = m.y + m.vy * lead
                dx, dy = tx - bx, ty - by
                d = math.hypot(dx, dy)
                if d < 3:
                    continue
                for pw in (clampf(d / 40.0, 0.3, 1.0), clampf(d / 28.0, 0.35, 1.0)):
                    cands.append((dx / d, dy / d, pw))
        for i in range(16):
            a = i * math.pi / 8
            c, s = math.cos(a), math.sin(a)
            for pw in (0.2, 0.32, 0.45):
                cands.append((c, s, pw))
            cands.append((c, s, 1.0))
        best = None
        bestv = -1e9
        for ux, uy, pw in cands:
            v = self.evaluate(k, mine, theirs, bx, by, bvx + ux * pw * KICK, bvy + uy * pw * KICK)
            if v > bestv:
                bestv = v
                best = (ux, uy, pw)
        ux, uy, pw = best
        return PlayerAction(movement=(ux, uy), kick_direction=(ux, uy), kick_power=pw)
