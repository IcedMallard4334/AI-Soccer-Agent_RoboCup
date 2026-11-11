"""v1: simulation-based kick evaluation + intercept-based chasing."""

import math

from soccer import PlayerAction, TeamAction, TeamController

DT = 0.05
F = 0.985
VMAX = 8.0
ACC = 20.0
KICK = 22.0
BALL_CAP = 30.0
KR = 2.2          # kick range
XL = 50.0
YL = 30.0
GH = 7.0          # goal half width
BR = 0.45
WALL_E = 0.75
HORIZON = 70


def clampf(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ball_path(px, py, vx, vy, n):
    """Predicted ball positions for ticks 1..n. Returns (points, goal_tick, goal_side)."""
    pts = []
    xm = XL - BR
    ym = YL - BR
    for t in range(1, n + 1):
        px += vx * DT
        py += vy * DT
        vx *= F
        vy *= F
        if py > ym:
            py = 2 * ym - py
            vy = -vy * WALL_E
        elif py < -ym:
            py = -2 * ym - py
            vy = -vy * WALL_E
        if px > xm:
            if abs(py) < GH:
                if px >= XL:
                    pts.append((px, py))
                    return pts, t, 1
            else:
                px = 2 * xm - px
                vx = -vx * WALL_E
        elif px < -xm:
            if abs(py) < GH:
                if px <= -XL:
                    pts.append((px, py))
                    return pts, t, -1
            else:
                px = -2 * xm - px
                vx = -vx * WALL_E
        pts.append((px, py))
        if vx * vx + vy * vy < 0.04:
            # Ball has effectively stopped; pad nothing, callers treat the last
            # point as resting.
            break
    return pts, None, 0


def reach_ticks(px, py, vx, vy, tx, ty, r):
    """Approximate ticks for a player to get within r of (tx, ty)."""
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


def first_intercept(body, pts, r, start=0, limit=None):
    """Earliest tick index at which body can be within r of the ball path."""
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
        # Skip ahead: can't possibly arrive sooner than t ticks.
        gap = int(t - (i + 1))
        i += 1 if gap < 2 else min(gap // 2, 6)
    if pts and (limit is None or limit >= len(pts)):
        # Ball comes to rest: time to reach the resting point.
        bx, by = pts[-1]
        t = reach_ticks(x, y, vx, vy, bx, by, r)
        return max(t, len(pts)), bx, by
    return None, None, None


class MyTeam(TeamController):
    name = "v1"
    version = "1"

    def initial_formation(self, field):
        return [
            (-48.0, 0.0),
            (-28.0, -10.0),
            (-28.0, 10.0),
            (-9.5, -1.5),
            (-14.0, 12.0),
        ]

    def reset(self, seed):
        pass

    # ------------------------------------------------------------------
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

        # Intercepts for everyone.
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
        # Keeper takes the ball when it is in his area and he is clearly first.
        if kt is not None and kt < best and my_ic[0][1] is not None and my_ic[0][1] < -38 and abs(my_ic[0][2]) < 16:
            chaser = keeper
            best = kt

        we_first = best < opp_best

        used = set()
        # 1) Anyone who can kick right now does something with the ball.
        kicker_done = False
        for b in sorted(mine, key=lambda q: (q.x - bx) ** 2 + (q.y - by) ** 2):
            if not dead or not their_kickoff:
                if obs.can_kick(b.id) and not their_kickoff:
                    act = self.choose_kick(b, mine, theirs, bx, by, bvx, bvy)
                    actions.set(b.id, act)
                    used.add(b.id)
                    kicker_done = True
                    break

        # 2) Chaser goes to the intercept point.
        if chaser is not None and chaser.id not in used and not their_kickoff:
            _, ix, iy = my_ic[chaser.id]
            if ix is None:
                ix, iy = bx, by
            tx, ty = self.approach_point(chaser, ix, iy)
            actions.set(chaser.id, PlayerAction(movement=self.toward(chaser, tx, ty)))
            used.add(chaser.id)

        # 3) Keeper.
        if 0 not in used:
            actions.set(0, PlayerAction(movement=self.keeper_move(keeper, bx, by, pts, gtick, gside)))
            used.add(0)

        # 4) The rest: shape.
        rest = [b for b in field_players if b.id not in used]
        spots = self.shape_spots(we_first, bx, by, theirs, len(rest), opp_best_body)
        assign = self.assign(rest, spots)
        for b, (tx, ty) in assign:
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
        """Arrive slightly behind the ball relative to the opponent goal."""
        gx, gy = XL, 0.0
        dx, dy = gx - ix, gy - iy
        d = math.hypot(dx, dy) or 1.0
        ox, oy = ix - dx / d * 0.8, iy - dy / d * 0.8
        # Only bother when we are already close; otherwise straight at it.
        if math.hypot(b.x - ix, b.y - iy) > 6:
            return ix, iy
        return ox, oy

    def keeper_move(self, k, bx, by, pts, gtick, gside):
        # Shot coming at our goal: get on its line.
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
        # Otherwise stand on the line ball -> goal centre.
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
            # Block the ball's route to goal, then mark the most dangerous.
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

    # ------------------------------------------------------------------
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
        pts, gt, gs = ball_path(bx, by, vx, vy, HORIZON)
        if not pts:
            return -9.0
        r = KR - 0.35
        horizon = gt if gt is not None else len(pts)
        ot = 1e9
        opx = opy = None
        for o in theirs:
            t, px, py = first_intercept(o, pts, r, 0, horizon if gt is not None else None)
            if t is not None and t < ot:
                ot, opx, opy = t, px, py
        mt = 1e9
        mpx = mpy = None
        for m in mine:
            start = 5 if m.id == kicker.id else 0
            t, px, py = first_intercept(m, pts, r, start, horizon if gt is not None else None)
            if t is not None and t < mt:
                mt, mpx, mpy = t, px, py
        if gs == 1:
            margin = ot - gt
            p = 1.0 / (1.0 + math.exp(-(margin - 1.0) / 2.0))
            return p * 4.0 + (1 - p) * (-0.4)
        if gs == -1:
            return -10.0
        if mt < ot:
            margin = ot - mt
            p = 1.0 / (1.0 + math.exp(-(margin - 2.0) / 2.5))
            keep = self.pos_value(mpx, mpy)
            lose = self.lose_value(mpx, mpy)
            return p * keep + (1 - p) * lose
        if opx is None:
            return -1.0
        return self.lose_value(opx, opy)

    def choose_kick(self, k, mine, theirs, bx, by, bvx, bvy):
        cands = []
        # Shots
        for gy in (-5.5, -3.5, -1.5, 1.5, 3.5, 5.5):
            dx, dy = XL + 1.0 - bx, gy - by
            d = math.hypot(dx, dy)
            cands.append((dx / d, dy / d, 1.0))
        # Passes to team-mates (lead a little in the direction they run).
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
        # Dribble touches and clearances
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
        # Follow the ball after striking it.
        return PlayerAction(movement=(ux, uy), kick_direction=(ux, uy), kick_power=pw)
