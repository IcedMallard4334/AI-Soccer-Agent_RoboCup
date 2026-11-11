"""v7: v6 + expected-goals map in the position value.

v6: exact player motion model, velocity controller, post-move kick reach,
restart tracking, optimised keeper, pitch-control support, lane defence."""

import math
import time
from bisect import bisect_left

from soccer import PlayerAction, TeamAction, TeamController

DT = 0.05
F = 0.985
VMAX = 8.0
DAMP = 0.9
KICK = 22.0
BALL_CAP = 30.0
KR = 2.2
XL = 50.0
YL = 30.0
GH = 7.0
BR = 0.45
XM = XL - BR
YM = YL - BR
PXM = 49.0
PYM = 29.0
WALL_E = 0.75
HORIZON = 80
ROLL = DT / (1 - F)
LNF = math.log(F)
CIRCLE = 9.0

NMAX = 400
# Drift of a player's current velocity after n ticks with no input: v*AD[n].
AD = [DT * 9.0 * (1 - DAMP ** n) for n in range(NMAX + 1)]
# Distance covered from standstill at full throttle in n ticks (speed capped).
DREST = [0.0]
_v = 0.0
for _n in range(NMAX):
    _v = min(VMAX, _v * DAMP + 1.0)
    DREST.append(DREST[-1] + _v * DT)
SPD = [VMAX * DT * n for n in range(NMAX + 1)]


def rest_ticks(d):
    """Ticks from standstill to cover distance d."""
    if d <= 0:
        return 0
    return bisect_left(DREST, d)

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
    "sup_every": 3,
    "sup_v": 1.0,
    "sup_lane": 0.12,
    "sup_open": 0.05,
    "sup_dist": 0.02,
    "rear_depth": 22.0,
    "cover_dist": 7.0,
    "mark_goal_side": 2.0,
    "mark_ball_frac": 0.25,
    "gk_speed": 28.0,
    "gk_r": 1.9,
    "gk_max": 12.0,
    "gk_mode": 1,
    "arrive_gain": 2.5,
    "budget": 0.009,
    "xg_w": 0.6,
    "xg_sig": 2.0,
    "xg_bias": 0.5,
    "pos_goal7": 0.6,
}


XG_X0 = 0.0
XG_STEP = 2.5
XG_NX = 21
XG_NY = 13


def clampf(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ball_path(px, py, vx, vy, n):
    """Exact free-ball prediction for ticks 1..n: (points, goal_tick, side)."""
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
        if -GH <= py <= GH:
            if px > XL:
                pts.append((px, py))
                return pts, t, 1
            if px < -XL:
                pts.append((px, py))
                return pts, t, -1
        else:
            if px > XM:
                px = 2 * XM - px
                vx = -vx * WALL_E
            elif px < -XM:
                px = -2 * XM - px
                vx = -vx * WALL_E
        pts.append((px, py))
        if vx * vx + vy * vy < 0.01:
            break
    return pts, None, 0


GT = [DT * (1 - F ** t) / (1 - F) for t in range(1, HORIZON + 1)]
GEND = GT[-1]


def fast_path(bx, by, vx, vy):
    """Like ball_path(.., HORIZON), closed form when no wall or goal is met."""
    ex = bx + vx * GEND
    ey = by + vy * GEND
    if -YM <= ey <= YM and -XM <= ex <= XM:
        return [(bx + vx * g, by + vy * g) for g in GT], None, 0
    return ball_path(bx, by, vx, vy, HORIZON)


def can_reach(px, py, vx, vy, qx, qy, r, n):
    """Whether a player can be within r of (qx, qy) after n ticks."""
    if n > NMAX:
        n = NMAX
    R = r + SPD[n]
    dx = qx - px
    dy = qy - py
    if dx * dx + dy * dy > R * R:
        return False
    a = AD[n]
    dx -= vx * a
    dy -= vy * a
    R = r + DREST[n]
    return dx * dx + dy * dy <= R * R


def reach_ticks(px, py, vx, vy, qx, qy, r):
    """Fewest ticks for a player to get within r of (qx, qy)."""
    d = math.hypot(qx - px, qy - py) - r
    if d <= 0:
        return 0
    n = int(d / (VMAX * DT))
    while n < NMAX:
        if can_reach(px, py, vx, vy, qx, qy, r, n):
            return n
        n += 1
    return NMAX


class Body:
    __slots__ = ("id", "x", "y", "vx", "vy", "cd")

    def __init__(self, p):
        self.id = p.id
        self.x, self.y = p.position
        self.vx, self.vy = p.velocity
        self.cd = p.kick_cooldown_ticks


def first_intercept(b, pts, r, start=0, limit=None, delay=0, step=1.5):
    """Earliest tick t (1-based, t < limit) at which b can be within r of the
    ball path. `step` bounds how far the ball moves per tick, for skipping."""
    n = len(pts)
    capped = limit is not None and limit <= n
    if capped:
        n = int(limit) - 1
    x, y, vx, vy = b.x, b.y, b.vx, b.vy
    close = step + VMAX * DT
    i = start
    while i < n:
        t = i + 1 - delay
        qx, qy = pts[i]
        if t >= 0:
            tt = t if t < NMAX else NMAX
            R = r + SPD[tt]
            dx = qx - x
            dy = qy - y
            d2 = dx * dx + dy * dy
            if d2 <= R * R:
                a = AD[tt]
                ex = dx - vx * a
                ey = dy - vy * a
                R2 = r + DREST[tt]
                e2 = ex * ex + ey * ey
                if e2 <= R2 * R2:
                    return i + 1, qx, qy
                gap = math.sqrt(e2) - R2
            else:
                gap = math.sqrt(d2) - R
        else:
            gap = math.hypot(qx - x, qy - y) - r
        k = int(gap / close)
        i += k if k > 1 else 1
    if pts and not capped:
        qx, qy = pts[-1]
        t = reach_ticks(x, y, vx, vy, qx, qy, r) + delay
        if t < len(pts):
            t = len(pts)
        if limit is None or t < limit:
            return t, qx, qy
    return None, None, None


def drive(b, tx, ty, gain=2.5, speed=VMAX):
    """Movement that steers b's velocity onto a velocity towards (tx, ty)
    (full speed far away, slowing to arrive), cancelling drift."""
    dx = tx - b.x
    dy = ty - b.y
    d = math.hypot(dx, dy)
    if d < 1e-6:
        mx, my = -DAMP * b.vx, -DAMP * b.vy
    else:
        s = min(speed, gain * d)
        mx = dx / d * s - DAMP * b.vx
        my = dy / d * s - DAMP * b.vy
    m = math.hypot(mx, my)
    if m > 1.0:
        mx /= m
        my /= m
    return mx, my


def after_move(b, mx, my):
    vx = b.vx * DAMP + mx
    vy = b.vy * DAMP + my
    s = math.hypot(vx, vy)
    if s > VMAX:
        vx *= VMAX / s
        vy *= VMAX / s
    return b.x + vx * DT, b.y + vy * DT


def ball_ticks(dist, speed):
    q = 1.0 - dist / (ROLL * speed)
    if q <= 0.0:
        return 999.0
    return math.log(q) / LNF


class MyTeam(TeamController):
    name = "v7"
    version = "7"

    def __init__(self):
        self.p = dict(P)
        self._reset_state()

    def _reset_state(self):
        if not hasattr(self, "xg"):
            self.xg = None
        self.chaser_id = None
        self.sup_cache = None
        self.sup_tick = -100
        self.restart = None      # (start_tick, kicking_team, length)
        self.threat = (0.0, 0.0)

    def initial_formation(self, field):
        if self.xg is None:
            self.build_xg()
        return [
            (-48.5, 0.0),
            (-30.0, -9.0),
            (-30.0, 9.0),
            (-11.4, -0.5),
            (-14.0, 13.0),
        ]

    def reset(self, seed):
        self._reset_state()
        if self.xg is None:
            self.build_xg()

    # ------------------------------------------------------------------
    def update_restart(self, obs):
        tick = obs.tick
        if tick == 0:
            self.restart = (0, obs.ball.controlling_team, 60)
        for ev in obs.events:
            k = ev.get("kind")
            if k == "goal":
                self.restart = (tick, obs.ball.controlling_team, 59)
            elif k == "kick" and self.restart is not None and ev.get("team") == self.restart[1]:
                self.restart = None
        if self.restart is not None and tick - self.restart[0] > self.restart[2] + 1:
            self.restart = None

    def act(self, obs):
        self.t0 = time.perf_counter()
        p = self.p
        ball = obs.ball
        bx, by = ball.position
        bvx, bvy = ball.velocity
        mine = [Body(q) for q in obs.my_players]
        theirs = [Body(q) for q in obs.opponents]
        actions = TeamAction()
        tick = obs.tick
        self.update_restart(obs)
        their_kickoff = self.restart is not None and self.restart[1] == 1

        pts, gtick, gside = ball_path(bx, by, bvx, bvy, HORIZON)
        if not pts:
            pts = [(bx, by)]
        bstep = math.hypot(bvx, bvy) * DT + 0.05

        r = p["r_get"]
        my_ic = {b.id: first_intercept(b, pts, r, step=bstep) for b in mine}
        opp_ic = {b.id: first_intercept(b, pts, r, step=bstep) for b in theirs}
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
            kicker = None
            kmove = None
            for b in sorted(mine, key=lambda q: (q.x - bx) ** 2 + (q.y - by) ** 2):
                if b.cd > 0:
                    continue
                if obs.can_kick(b.id):
                    kicker = b
                    break
                mx, my = drive(b, bx, by, 100.0)
                nx, ny = after_move(b, mx, my)
                if (nx - bx) ** 2 + (ny - by) ** 2 <= (KR - 0.05) ** 2:
                    kicker = b
                    kmove = (mx, my)
                    break
            if kicker is not None:
                actions.set(kicker.id, self.choose_kick(kicker, kmove, mine, theirs,
                                                        bx, by, bvx, bvy))
                used.add(kicker.id)

        if chaser is not None and chaser.id not in used and not their_kickoff:
            _, ix, iy = my_ic[chaser.id]
            if ix is None:
                ix, iy = bx, by
            tx, ty = self.approach_point(chaser, ix, iy)
            actions.set(chaser.id, PlayerAction(movement=drive(chaser, tx, ty, 100.0)))
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
            if chaser is not None and my_ic[chaser.id][1] is not None:
                hx, hy = my_ic[chaser.id][1], my_ic[chaser.id][2]
            else:
                hx, hy = bx, by
            plan = self.support_plan(rest, theirs, hx, hy, tick)
        else:
            plan = self.defence_plan(rest, theirs, bx, by, opp_first, opp_ic)
        gain = p["arrive_gain"]
        for b, (tx, ty) in plan:
            if their_kickoff:
                tx, ty = self.outside_circle(tx, ty)
            actions.set(b.id, PlayerAction(movement=drive(b, tx, ty, gain)))
        if their_kickoff:
            self.keep_out(actions, mine)
        return actions

    # ------------------------------------------------------------------
    @staticmethod
    def outside_circle(x, y, rad=11.0):
        d = math.hypot(x, y)
        if d >= rad:
            return x, y
        if d < 1e-6:
            return -rad, 0.0
        return x / d * rad, y / d * rad

    def keep_out(self, actions, mine):
        """No player may end the tick inside the centre circle."""
        for b in mine:
            a = actions.players.get(b.id)
            mx, my = a.movement if a is not None else (0.0, 0.0)
            nx, ny = after_move(b, mx, my)
            if nx * nx + ny * ny < (CIRCLE + 1.2) ** 2:
                tx, ty = self.outside_circle(b.x, b.y, CIRCLE + 3.0)
                if math.hypot(b.x, b.y) >= CIRCLE + 3.0:
                    tx, ty = b.x, b.y
                actions.set(b.id, PlayerAction(movement=drive(b, tx, ty, 4.0)))

    @staticmethod
    def approach_point(b, ix, iy):
        dx, dy = XL - ix, -iy
        d = math.hypot(dx, dy) or 1.0
        if math.hypot(b.x - ix, b.y - iy) > 6:
            return ix, iy
        return ix - dx / d * 0.8, iy - dy / d * 0.8

    # ------------------------------------------------------------------
    def keeper_spot(self, tx, ty):
        p = self.p
        ax, ay = -XL - tx, GH - ty
        cx, cy = -XL - tx, -GH - ty
        la = math.hypot(ax, ay) or 1.0
        lc = math.hypot(cx, cy) or 1.0
        ux, uy = ax / la + cx / lc, ay / la + cy / lc
        lu = math.hypot(ux, uy) or 1.0
        ux, uy = ux / lu, uy / lu
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
            dfs = dg - s
            if dfs < 2.0:
                break
            kx = tx + ux * dfs
            ky = ty + uy * dfs
            if kx < -XL + 1.0:
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
                tk = rest_ticks(h - p["gk_r"]) + 1.0
                if tb - tk < m:
                    m = tb - tk
            if m > bestm:
                bestm = m
                best = (kx, ky)
            s += 0.8
        if best is None:
            return -XL + 1.0, clampf(ty, -GH + 1.0, GH - 1.0)
        return best

    def keeper_move(self, k, bx, by, pts, gtick, gside):
        if gside == -1 and gtick is not None:
            best = None
            for i, (px, py) in enumerate(pts):
                if can_reach(k.x, k.y, k.vx, k.vy, px, py, 1.3, i + 1):
                    best = (px, py)
                    break
            if best is None:
                best = pts[-1]
            return drive(k, best[0], best[1], 100.0)
        if self.p["gk_mode"] == 0:
            gx = -XL
            dx, dy = bx - gx, by
            d = math.hypot(dx, dy) or 1.0
            depth = clampf(d * 0.12, 1.5, 4.0)
            tx = max(gx + dx / d * depth, -XL + 1.2)
            ty = clampf(dy / d * depth * 2.0 + by * 0.12, -GH + 1.0, GH - 1.0)
            return drive(k, tx, ty, 3.0)
        tx, ty = self.threat
        kx, ky = self.keeper_spot(tx, ty)
        return drive(k, kx, ky, 3.0)

    # ------------------------------------------------------------------
    def support_plan(self, bodies, theirs, hx, hy, tick):
        p = self.p
        out = []
        free = list(bodies)
        if not free:
            return out
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
        p = self.p
        out = []
        free = list(bodies)
        if not free:
            return out
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
            danger.append((math.hypot(o.x + XL, o.y), o))
        danger.sort(key=lambda t: t[0])
        for _, o in danger:
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
    def build_xg(self):
        """Scoring chance of a 28 u/s shot from each cell against an ideally
        placed keeper (our own keeper model, mirrored)."""
        p = self.p
        tab = []
        for ix in range(XG_NX):
            px = XG_X0 + ix * XG_STEP
            row = []
            for iy in range(XG_NY):
                py = iy * XG_STEP
                tx, ty = -px, py
                kx, ky = self.keeper_spot(tx, ty)
                m = 1e9
                for gy in (GH - 0.6, -GH + 0.6):
                    lx, ly = -XL - tx, gy - ty
                    ll = math.hypot(lx, ly)
                    lx /= ll
                    ly /= ll
                    along = (kx - tx) * lx + (ky - ty) * ly
                    h = abs((kx - tx) * ly - (ky - ty) * lx)
                    mm = ball_ticks(max(along, 0.0), 28.0) - (rest_ticks(h - 1.9) + 1)
                    if mm < m:
                        m = mm
                z = (m - p["xg_bias"]) / p["xg_sig"]
                z = clampf(z, -30.0, 30.0)
                row.append(1.0 / (1.0 + math.exp(z)))
            tab.append(row)
        self.xg = tab

    def xg_at(self, x, y):
        ix = int((x - XG_X0) / XG_STEP + 0.5)
        if ix < 0:
            return 0.0
        if ix >= XG_NX:
            ix = XG_NX - 1
        iy = int(abs(y) / XG_STEP + 0.5)
        if iy >= XG_NY:
            iy = XG_NY - 1
        return self.xg[ix][iy]

    def pos_value(self, x, y):
        p = self.p
        dg = math.hypot(XL - x, y)
        return (p["pos_prog"] * (x / XL) + p["pos_goal7"] * math.exp(-dg / p["goal_len"])
                + p["xg_w"] * self.xg_at(x, y))

    def lose_value(self, x, y):
        p = self.p
        dg = math.hypot(-XL - x, y)
        return -p["lose_base"] - p["lose_scale"] * math.exp(-dg / p["goal_len"])

    def evaluate(self, kicker, mine, theirs, bx, by, vx, vy):
        p = self.p
        pts, gt, gs = fast_path(bx, by, vx, vy)
        if not pts:
            return -9.0
        step = math.hypot(vx, vy) * DT + 0.05
        r = p["r_get"]
        lim = gt + 1 if gt is not None else None
        ot = lim
        opt = None
        react = int(p["react"])
        for o in theirs:
            t, px, py = first_intercept(o, pts, r, 0, ot, react, step)
            if t is not None:
                ot, opt = t, (px, py)
        mt = ot
        mpt = None
        for m in mine:
            t, px, py = first_intercept(m, pts, r, 5 if m.id == kicker.id else 0, mt, 0, step)
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

    def choose_kick(self, k, kmove, mine, theirs, bx, by, bvx, bvy):
        theirs = sorted(theirs, key=lambda o: (o.x - bx) ** 2 + (o.y - by) ** 2)
        mine = sorted(mine, key=lambda o: (o.x - bx) ** 2 + (o.y - by) ** 2)
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
        for i in (0, 1, 15, 2, 14, 3, 13, 4, 12, 5, 11, 6, 10, 7, 9, 8):
            a = i * math.pi / 8
            c, s = math.cos(a), math.sin(a)
            for sp in (6.0, 9.0, 12.0):
                targets.append((c, s, sp))
        for i in (0, 1, 15, 2, 14, 3, 13, 4, 12, 5, 11, 6, 10, 7, 9, 8):
            a = i * math.pi / 8
            targets.append((math.cos(a), math.sin(a), BALL_CAP))
        best = None
        bestv = -1e9
        budget = self.p["budget"]
        t0 = self.t0
        for ci, (ux, uy, sp) in enumerate(targets):
            if (ci & 1) and time.perf_counter() - t0 > budget:
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
            return PlayerAction(movement=kmove or (0.0, 0.0), kick_direction=(1.0, 0.0), kick_power=1.0)
        kx, ky, pw, ux, uy = best
        # The kick is judged after this tick's move: keep the ball in range.
        if kmove is None:
            mx, my = drive(k, k.x + ux * 10, k.y + uy * 10, 100.0)
            nx, ny = after_move(k, mx, my)
            if (nx - bx) ** 2 + (ny - by) ** 2 > (KR - 0.05) ** 2:
                mx, my = drive(k, bx, by, 100.0)
                nx, ny = after_move(k, mx, my)
                if (nx - bx) ** 2 + (ny - by) ** 2 > (KR - 0.05) ** 2:
                    mx, my = 0.0, 0.0
            kmove = (mx, my)
        return PlayerAction(movement=kmove, kick_direction=(kx, ky), kick_power=pw)
