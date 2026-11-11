"""Victor_Hyginus - a simulation-driven 5-a-side team.

How it decides, every tick:

* Physics. Ball and player motion are modelled exactly as the engine steps
  them (ball: move then x0.985 friction, mirrored wall bounces at 0.75;
  player: v = 0.9 v + move, capped at 8). From that, every player's earliest
  interception of the ball's predicted path is computed for both teams.
* Value. What a position is worth was measured, not guessed: the chance that
  the team holding the ball at each spot scores the next goal, learned from
  hundreds of evenly matched games (an "expected threat" grid, in goals).
* On the ball. Whoever can kick (judged after this tick's move, as the engine
  does) searches kicks coarse-to-fine: shots across the goal mouth, passes and
  through-balls, carry touches that keep the ball just ahead of the runner,
  dribbles and clearances. Each is rolled forward and scored by who reaches it
  first and where, in that same goal currency; the best few passes are also
  scored by the first-time shot they would set up. A time budget keeps every
  decision well inside the deadline.
* Off the ball. In attack one man holds back and the others go where they
  would beat every defender to a pass (pitch control). In defence one covers
  the ball's route to goal, the rest mark goal-side, and the opponent's next
  kick is predicted with our own evaluator so a defender can cut it off.
* Keeper. Stands on the bisector of the shooting angle at the depth that best
  covers both corners, and goes to meet any shot heading for goal.
* Game state. Chases the game when level or behind late on, protects a late
  one-goal lead, and shoots far more readily against a parked bus.
* Restarts. Tracks kickoffs exactly and never enters the centre circle while
  the opponents' restart is live.

Every parameter was tuned by playing thousands of matches against earlier
versions of this team and a set of sparring styles.
"""

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
    "r_get": 1.803,
    "sig_keep": 4.363,
    "keep_bias": 1.951,
    "sig_goal": 2.141,
    "goal_bias": 2.846,
    "goal_val": 4.0,
    "lose_base": 0.3,
    "lose_scale": 1.3,
    "pos_prog": 0.15,
    "pos_goal": 0.9,
    "goal_len": 14.0,
    "hyst": 6.0,
    "sup_every": 3,
    "sup_v": 1.0,
    "sup_lane": 0.175,
    "sup_open": 0.28,
    "sup_dist": 0.02,
    "rear_depth": 22.0,
    "cover_dist": 14.561,
    "mark_goal_side": 1.7,
    "mark_ball_frac": 0.25,
    "gk_speed": 28.0,
    "gk_r": 1.9,
    "gk_max": 12.0,
    "gk_mode": 1,
    "arrive_gain": 2.5,
    "budget": 0.009,
    "xg_w": 0.0,
    "xg_sig": 2.0,
    "xg_bias": 0.5,
    "pos_goal7": 0.9,
    "carry_lead": 2.121,
    "carry_dirs": 12,
    "through": (6.0, 12.0),
    "press2_x": -999.0,
    "press2_gap": 12.0,
    "contest_pen": 0.0,
    "shot_n": 9,
    "leads": (0.0, 0.5, 1.0),
    "vends": (5.0, 10.0),
    "drib_n": 16,
    "drib_speeds": (6.0, 9.0, 12.0),
    "clear_n": 16,
    "shot_stop": 0.9,
    "c_leads": (0.0, 0.7),
    "c_vends": (7.0,),
    "c_through": (8.0,),
    "c_drib_n": 8,
    "c_drib_speeds": (7.0, 11.0),
    "c_clear_n": 8,
    "c_carry_n": 8,
    "refine_k": 4,
    "refine_da": 0.2,
    "refine_dc": 0.39,
    "xt_scale": 2.5,
    "goal_units": 1.389,
    "lose_cap": -0.02,
    "lose_pen": 0.089,
    "antic": 1,
    "antic_t": 6.447,
    "use_cd": 0,
    "la_k": 2.716,
    "la_x": 10.0,
    "la_head": 0.7,
    "la_w": 0.85,
    "la_ys": (-6.0, -3.0, 0.0, 3.0, 6.0),
    # game state: (time_remaining below which it applies, overrides)
    "gs_late": 0.5,
    "gs_chase": {"goal_units": 2.0, "lose_pen": 0.0, "keep_bias": 1.0},
    "gs_protect": {"lose_pen": 0.25, "goal_units": 1.0},
    "pc": 1,
    "pc_sig": 3.0,
    "pc_lane": 0.05,
    "pc_delay": 3.0,
    "pc_every": 3,
    "guard": 0.6,
    "bus_x": 36.0,
    "bus_n": 2.5,
    "bus_ema": 0.01,
    "bus_mode": {"goal_bias": 0.0},
}


def fan(n):
    """n unit directions, the most forward first."""
    out = []
    for i in range(n):
        a = i * 2.0 * math.pi / n
        if a > math.pi:
            a -= 2.0 * math.pi
        out.append((abs(a), math.cos(a), math.sin(a)))
    out.sort()
    return [(c, s) for _, c, s in out]

G5 = DT * (1 - F ** 5) / (1 - F)


XG_X0 = 0.0
XG_STEP = 2.5
XG_NX = 21
XG_NY = 13


# Value, in goals, of having the ball at (x, |y|) for the team in possession:
# rows are x bins of 5 units from -50, columns |y| bins of 5 units.
XT = [(-0.288, -0.176, -0.11, -0.083, -0.073, -0.082), (-0.172, -0.136, -0.092, -0.064, -0.054, -0.063), (-0.126, -0.101, -0.061, -0.033, -0.029, -0.035), (-0.093, -0.077, -0.042, -0.015, -0.014, -0.016), (-0.06, -0.049, -0.027, -0.011, -0.008, -0.013), (-0.024, -0.025, -0.014, -0.007, -0.01, -0.013), (-0.0, 0.001, -0.001, 0.005, 0.002, -0.003), (0.007, 0.015, 0.02, 0.016, 0.012, 0.011), (0.021, 0.03, 0.03, 0.021, 0.01, 0.012), (0.02, 0.023, 0.028, 0.021, 0.012, 0.007), (0.021, 0.029, 0.033, 0.03, 0.019, 0.013), (0.034, 0.035, 0.042, 0.036, 0.024, 0.018), (0.062, 0.064, 0.054, 0.043, 0.028, 0.021), (0.071, 0.062, 0.052, 0.044, 0.028, 0.023), (0.091, 0.078, 0.055, 0.046, 0.034, 0.024), (0.124, 0.105, 0.067, 0.049, 0.031, 0.026), (0.16, 0.135, 0.091, 0.06, 0.038, 0.034), (0.218, 0.174, 0.108, 0.072, 0.047, 0.041), (0.373, 0.235, 0.121, 0.083, 0.059, 0.043), (0.558, 0.337, 0.132, 0.095, 0.064, 0.039)]


def xt(x, y):
    """Bilinear lookup in XT (cell centres at -47.5 + 5i, 2.5 + 5j)."""
    fx = (x + 47.5) / 5.0
    fy = (abs(y) - 2.5) / 5.0
    if fx < 0.0:
        fx = 0.0
    elif fx > 19.0:
        fx = 19.0
    if fy < 0.0:
        fy = 0.0
    elif fy > 5.0:
        fy = 5.0
    i = int(fx)
    j = int(fy)
    if i > 18:
        i = 18
    if j > 4:
        j = 4
    ax = fx - i
    ay = fy - j
    r0 = XT[i]
    r1 = XT[i + 1]
    return ((r0[j] * (1 - ay) + r0[j + 1] * ay) * (1 - ax)
            + (r1[j] * (1 - ay) + r1[j + 1] * ay) * ax)


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
FPOW = [F ** t for t in range(HORIZON + 2)]
GEND = GT[-1]


def fast_path(bx, by, vx, vy):
    """Like ball_path(.., HORIZON) but closed form when the ball meets no end
    wall and at most one side wall. Returns (pts, goal_tick, side, straight)."""
    ex = bx + vx * GEND
    ey = by + vy * GEND
    if -XM <= ex <= XM:
        if -YM <= ey <= YM:
            return [(bx + vx * g, by + vy * g) for g in GT], None, 0, True
        # One bounce off a side wall: mirror at the bounce tick, then the
        # remaining travel is scaled by the restitution.
        lim = YM if ey > 0 else -YM
        g_hit = (lim - by) / vy
        i = bisect_left(GT, g_hit)
        if i < HORIZON:
            yr = by + vy * GT[i]
            k = 2.0 * lim - yr + WALL_E * yr
            ys = [by + vy * g for g in GT[:i]]
            ys.extend([k - WALL_E * (by + vy * g) for g in GT[i:]])
            if max(ys) <= YM and min(ys) >= -YM:
                return list(zip([bx + vx * g for g in GT], ys)), None, 0, False
    pts, gt, gs = ball_path(bx, by, vx, vy, HORIZON)
    return pts, gt, gs, False


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
    __slots__ = ("id", "x", "y", "vx", "vy", "cd", "drift")

    def __init__(self, p):
        self.id = p.id
        self.x, self.y = p.position
        self.vx, self.vy = p.velocity
        self.cd = p.kick_cooldown_ticks
        self.drift = 0.45 * math.hypot(self.vx, self.vy)


class Mirror:
    """A player seen from the other team's side of the pitch."""
    __slots__ = ("id", "x", "y", "vx", "vy", "cd", "drift")

    def __init__(self, b):
        self.id = b.id
        self.x, self.y = -b.x, -b.y
        self.vx, self.vy = -b.vx, -b.vy
        self.cd = b.cd
        self.drift = b.drift


def first_intercept(b, pts, r, start=0, limit=None, delay=0, step=1.5):
    """Earliest tick t (1-based, t < limit) at which b can be within r of the
    ball path. `step` bounds how far the ball moves per tick, for skipping."""
    n = len(pts)
    capped = limit is not None and limit <= n
    if capped:
        n = int(limit) - 1
    x, y, vx, vy = b.x, b.y, b.vx, b.vy
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
        k = int(gap / (step * FPOW[i] + 0.45))
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
    name = "Victor_Hyginus"
    version = "23"

    def __init__(self):
        self.p = dict(P)
        self.base_p = self.p
        self._reset_state()

    def _reset_state(self):
        self.pc_cache = None
        self.deep = 0.0
        if not hasattr(self, "xg"):
            self.xg = None
        self.chaser_id = None
        self.sup_cache = None
        self.sup_tick = -100
        self.restart = None      # (start_tick, kicking_team, length)
        self.threat = (0.0, 0.0)

    def initial_formation(self, field):
        if self.xg is None and self.p["xg_w"] > 0:
            self.build_xg()
        return [
            (-48.5, 0.0),
            (-30.0, -9.0),
            (-30.0, 9.0),
            (-11.4, -0.5),
            (-14.0, 13.0),
        ]

    def reset(self, seed):
        self.base_p = dict(self.p)
        self._reset_state()
        if self.xg is None and self.p["xg_w"] > 0:
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
        try:
            return self.decide(obs)
        except Exception:
            return self.fallback(obs)

    @staticmethod
    def fallback(obs):
        """Plain chase-and-shoot, used only if decide() ever raises."""
        actions = TeamAction()
        bx, by = obs.ball.position
        for q in obs.my_players:
            x, y = q.position
            dx, dy = bx - x, by - y
            d = math.hypot(dx, dy) or 1.0
            if obs.can_kick(q.id):
                gx, gy = XL - bx, -by
                g = math.hypot(gx, gy) or 1.0
                actions.set(q.id, PlayerAction(movement=(dx / d, dy / d),
                                               kick_direction=(gx / g, gy / g), kick_power=1.0))
            else:
                actions.set(q.id, PlayerAction(movement=(dx / d, dy / d)))
        return actions

    def decide(self, obs):
        self.t0 = time.perf_counter()
        self.p = self.base_p
        bp = self.base_p
        deep = 0
        for q in obs.opponents[1:]:
            if q.position[0] > bp["bus_x"]:
                deep += 1
        self.deep = self.deep + (deep - self.deep) * bp["bus_ema"]
        if self.deep >= bp["bus_n"]:
            self.p = dict(bp)
            self.p.update(bp["bus_mode"])
        if obs.time_remaining < self.base_p["gs_late"]:
            mine_g, theirs_g = obs.score
            over = None
            if mine_g <= theirs_g:
                over = self.base_p["gs_chase"]
            elif mine_g - theirs_g == 1:
                over = self.base_p["gs_protect"]
            if over:
                self.p = dict(self.p)
                self.p.update(over)
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
        if (p["antic"] and not attacking and not their_kickoff and opp_first is not None
                and time.perf_counter() - self.t0 < p["budget"] * p["guard"]
                and opp_best <= p["antic_t"] and rest
                and opp_ic[opp_first.id][1] is not None):
            got = self.anticipate(opp_first, opp_ic[opp_first.id], int(opp_best), pts,
                                  mine, theirs, rest)
            if got is not None:
                b, tx, ty = got
                actions.set(b.id, PlayerAction(movement=drive(b, tx, ty, 100.0)))
                used.add(b.id)
                rest = [q for q in rest if q.id != b.id]
        if (not attacking and not their_kickoff and opp_first is not None
                and opp_ic[opp_first.id][1] is not None
                and opp_ic[opp_first.id][1] < p["press2_x"] and len(rest) >= 3):
            hx, hy = opp_ic[opp_first.id][1], opp_ic[opp_first.id][2]
            cand = None
            ct = 1e9
            for b in rest:
                t = my_ic[b.id][0]
                if t is not None and t < ct:
                    ct, cand = t, b
            if cand is not None and ct - opp_best < p["press2_gap"]:
                # Come from the goal side of where they will receive it.
                gx, gy = -XL - hx, -hy
                gl = math.hypot(gx, gy) or 1.0
                tx, ty = hx + gx / gl * 1.5, hy + gy / gl * 1.5
                actions.set(cand.id, PlayerAction(movement=drive(cand, tx, ty, 100.0)))
                used.add(cand.id)
                rest = [b for b in rest if b.id != cand.id]
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
        if p["pc"]:
            ids = tuple(b.id for b in free)
            c = self.pc_cache
            if (c is not None and c[0] == ids and tick - c[1] < p["pc_every"]
                    and abs(c[2] - hx) + abs(c[3] - hy) < 3.0):
                tg = c[4]
                return out + [(b, tg[b.id]) for b in free]
            res = self.pc_assign(free, theirs, hx, hy)
            self.pc_cache = (ids, tick, hx, hy, {b.id: t for b, t in res})
            return out + res
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

    def pc_assign(self, free, theirs, hx, hy):
        """Pitch control: each supporter takes the spot where, once a pass
        from (hx, hy) arrives, he is there before any defender; weighted by
        the value of having the ball there. Spots are kept 10 apart."""
        p = self.p
        r = p["r_get"]
        sig = p["pc_sig"]
        spots = []
        x0 = clampf(hx - 12.0, -42.0, 38.0)
        for ix in range(9):
            sx = x0 + ix * 5.0
            if sx > 46.0:
                break
            for iy in range(9):
                sy = -24.0 + iy * 6.0
                dx, dy = sx - hx, sy - hy
                L = math.hypot(dx, dy)
                if L < 6.0:
                    continue
                tb = ball_ticks(L, 8.0 + L / ROLL) + p["pc_delay"]
                tthem = 1e9
                lane = 10.0
                ux, uy = dx / L, dy / L
                for o in theirs:
                    t = reach_ticks(o.x, o.y, o.vx, o.vy, sx, sy, r)
                    if t < tthem:
                        tthem = t
                    ox, oy = o.x - hx, o.y - hy
                    u = ox * ux + oy * uy
                    if 0.0 < u < L:
                        m = abs(ox * uy - oy * ux) - (1.5 + 0.22 * u)
                        if m < lane:
                            lane = m
                spots.append((sx, sy, tb, tthem, self.pos_value(sx, sy) + p["pc_lane"] * clampf(lane, -5.0, 5.0)))
        out = []
        chosen = []
        for b in free:
            bestv = -1e9
            bests = (b.x, b.y)
            for sx, sy, tb, tthem, v0 in spots:
                ok = True
                for cx, cy in chosen:
                    if (cx - sx) ** 2 + (cy - sy) ** 2 < 100.0:
                        ok = False
                        break
                if not ok:
                    continue
                tus = reach_ticks(b.x, b.y, b.vx, b.vy, sx, sy, r)
                arrive = tb if tb > tus else tus
                z = (tthem - arrive) / sig
                if z > 30.0:
                    z = 30.0
                elif z < -30.0:
                    z = -30.0
                v = v0 / (1.0 + math.exp(-z))
                if v > bestv:
                    bestv = v
                    bests = (sx, sy)
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
        return self.p["xt_scale"] * xt(x, y)

    def lose_value(self, x, y):
        v = xt(-x, y)
        cap = self.p["lose_cap"]
        if v < cap:
            v = cap
        return -self.p["xt_scale"] * v - self.p["lose_pen"]

    def evaluate(self, kicker, mine, theirs, bx, by, vx, vy):
        p = self.p
        self._rec = None
        pts, gt, gs, straight = fast_path(bx, by, vx, vy)
        if not pts:
            return -9.0
        sp = math.hypot(vx, vy)
        step = sp * DT + 0.05
        r = p["r_get"]
        if straight and sp > 1e-6:
            ux, uy = vx / sp, vy / sp
            L = sp * GEND
            ex, ey = pts[-1]
        else:
            straight = False
        lim = gt + 1 if gt is not None else None
        react = int(p["react"])
        if straight:
            # Lower bound on each player's intercept tick from his distance to
            # the ball's line; check the likeliest first, prune the rest.
            def lower_bounds(group):
                out = []
                for b in group:
                    rx, ry = b.x - bx, b.y - by
                    a = rx * ux + ry * uy
                    if a <= 0.0:
                        dmin = math.sqrt(rx * rx + ry * ry)
                    elif a >= L:
                        dmin = math.hypot(b.x - ex, b.y - ey)
                    else:
                        dmin = abs(rx * uy - ry * ux)
                    out.append(((dmin - r - b.drift) * 2.5, b))
                out.sort(key=lambda e: e[0])
                return out
            olist = lower_bounds(theirs)
            mlist = lower_bounds(mine)
        else:
            olist = [(-1e9, b) for b in theirs]
            mlist = [(-1e9, b) for b in mine]
        ot = lim
        opt = None
        usecd = p["use_cd"]
        for lb, o in olist:
            if ot is not None and lb >= ot:
                break
            t, px, py = first_intercept(o, pts, r, o.cd if usecd else 0, ot, react, step)
            if t is not None:
                ot, opt = t, (px, py)
        mt = ot
        mpt = None
        kid = kicker.id
        for lb, m in mlist:
            if mt is not None and lb >= mt:
                break
            t, px, py = first_intercept(m, pts, r, 5 if m.id == kid else 0, mt, 0, step)
            if t is not None:
                mt, mpt = t, (px, py)
        if gs == 1:
            gv = p["xt_scale"] * p["goal_units"]
            if opt is None:
                return gv
            margin = ot - gt
            q = 1.0 / (1.0 + math.exp(-(margin - p["goal_bias"]) / p["sig_goal"]))
            return q * gv + (1 - q) * self.lose_value(*opt)
        if gs == -1 and opt is None and mpt is None:
            return -10.0
        if mpt is not None:
            margin = (ot - mt) if opt is not None else 30.0
            q = 1.0 / (1.0 + math.exp(-(margin - p["keep_bias"]) / p["sig_keep"]))
            i = int(mt) - 1
            if 1 <= i < len(pts):
                vix = (pts[i][0] - pts[i - 1][0]) / DT
                viy = (pts[i][1] - pts[i - 1][1]) / DT
            else:
                vix, viy = vx * 0.5, vy * 0.5
            self._rec = (q, mpt, mt, vix, viy)
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

    def anticipate(self, ok, ic, tr, pts, mine, theirs, rest):
        """Predict the kick opponent `ok` makes on receiving the ball at tick
        tr, and return (our player, x, y) to cut it off, or None."""
        p = self.p
        _, rx, ry = ic
        i = min(max(tr, 1), len(pts)) - 1
        if i >= 1:
            vix = (pts[i][0] - pts[i - 1][0]) / DT
            viy = (pts[i][1] - pts[i - 1][1]) / DT
        else:
            vix = viy = 0.0
        # Their view of the pitch: everything rotated by 180 degrees.
        them = [Mirror(o) for o in theirs]
        us = [Mirror(m) for m in mine]
        kk = None
        for o in them:
            if o.id == ok.id:
                kk = o
        if kk is None:
            return None
        # Place their kicker at the ball, as he will be when he receives it.
        mrx, mry = -rx, -ry
        dx, dy = mrx - kk.x, mry - kk.y
        d = math.hypot(dx, dy) or 1.0
        kk.x, kk.y = mrx - dx / d * 1.0, mry - dy / d * 1.0
        mvx, mvy = -vix, -viy
        best = None
        bestv = -1e9
        cands = []
        for si in range(5):
            gy = -6.0 + 3.0 * si
            ddx, ddy = XL - mrx, gy - mry
            dd = math.hypot(ddx, ddy)
            cands.append((ddx / dd, ddy / dd, BALL_CAP))
        for m in them:
            if m.id == kk.id:
                continue
            ddx, ddy = m.x - mrx, m.y - mry
            dd = math.hypot(ddx, ddy)
            if dd > 3:
                cands.append((ddx / dd, ddy / dd, 7.0 + dd / ROLL))
        for c, s2 in fan(8):
            cands.append((c, s2, 9.0))
            cands.append((c, s2, BALL_CAP))
        for ux, uy, sp in cands:
            kq = self.kick_for(mvx, mvy, ux, uy, sp)
            if kq is None:
                continue
            s3 = kq[3]
            v = self.evaluate(kk, them, us, mrx, mry, ux * s3, uy * s3)
            if v > bestv:
                bestv = v
                best = (ux * s3, uy * s3)
        if best is None:
            return None
        # Back to our frame; we have tr ticks before the kick happens.
        ppts, gt, gs = ball_path(rx, ry, -best[0], -best[1], HORIZON)
        if not ppts:
            return None
        r = p["r_get"]
        pick = None
        pt = 1e9
        for b in rest:
            t, ix, iy = first_intercept(b, ppts, r, 0, None, -tr, 1.6)
            if t is not None and t < pt:
                pt, pick = t, (b, ix, iy)
        return pick

    def shot_value_from(self, theirs, px, py, t, vix, viy):
        """Best first-time shot from (px, py) once the ball arrives there at
        tick t with velocity (vix, viy); defenders get a head start."""
        p = self.p
        head = -int(t * p["la_head"])
        r = p["r_get"]
        best = -1e9
        for gy in p["la_ys"]:
            dx, dy = XL - px, gy - py
            d = math.hypot(dx, dy)
            if d < 1e-6:
                continue
            ux, uy = dx / d, dy / d
            kk = self.kick_for(vix, viy, ux, uy, BALL_CAP)
            if kk is None:
                continue
            s2 = kk[3]
            pts, gt, gs = ball_path(px, py, ux * s2, uy * s2, HORIZON)
            if gs != 1:
                continue
            step = s2 * DT + 0.05
            ot = gt + 1
            for o in theirs:
                tt, _, _ = first_intercept(o, pts, r, 0, ot, head, step)
                if tt is not None:
                    ot = tt
            if ot > gt:
                q = 1.0
            else:
                q = 1.0 / (1.0 + math.exp(-((ot - gt) - p["goal_bias"]) / p["sig_goal"]))
            v = q * p["xt_scale"] * p["goal_units"] + (1 - q) * self.lose_value(XL - 2.0, gy)
            if v > best:
                best = v
        return best

    def carry_velocity(self, k, a, bx, by):
        """Ball velocity putting the ball carry_lead ahead of where k will be
        in 5 ticks running at angle a, and the movement to use now."""
        ux, uy = math.cos(a), math.sin(a)
        mvx, mvy = drive(k, k.x + ux * 20.0, k.y + uy * 20.0, 100.0)
        x, y, vx, vy = k.x, k.y, k.vx, k.vy
        mx, my = mvx, mvy
        for _ in range(5):
            vx = vx * DAMP + mx
            vy = vy * DAMP + my
            sp = math.hypot(vx, vy)
            if sp > VMAX:
                vx *= VMAX / sp
                vy *= VMAX / sp
            x += vx * DT
            y += vy * DT
            mx = ux * VMAX - DAMP * vx
            my = uy * VMAX - DAMP * vy
            mm = math.hypot(mx, my)
            if mm > 1.0:
                mx /= mm
                my /= mm
        lead = self.p["carry_lead"]
        return (x + ux * lead - bx) / G5, (y + uy * lead - by) / G5, mvx, mvy

    def choose_kick(self, k, kmove, mine, theirs, bx, by, bvx, bvy):
        theirs = sorted(theirs, key=lambda o: (o.x - bx) ** 2 + (o.y - by) ** 2)
        mine = sorted(mine, key=lambda o: (o.x - bx) ** 2 + (o.y - by) ** 2)
        pp = self.p
        budget = pp["budget"]
        t0 = self.t0
        stop_v = pp["xt_scale"] * pp["goal_units"] * pp["shot_stop"]
        state = {"best": None, "bestv": -1e9, "done": False}
        scored = []   # (value, kind, angle, speed) of non-shot candidates
        recs = []     # (value, reception info, action) of kept-ball candidates

        def over():
            if state["done"]:
                return True
            if time.perf_counter() - t0 > budget:
                state["done"] = True
            return state["done"]

        def try_t(ux, uy, sp, record):
            kk = self.kick_for(bvx, bvy, ux, uy, sp)
            if kk is None:
                return
            kx, ky, pw, s2 = kk
            v = self.evaluate(k, mine, theirs, bx, by, ux * s2, uy * s2)
            if record:
                scored.append((v, "t", math.atan2(uy, ux), sp))
            act = (kx, ky, pw, ux, uy, None)
            if self._rec is not None:
                recs.append((v, self._rec, act))
            if v > state["bestv"]:
                state["bestv"] = v
                state["best"] = act
                if v >= stop_v:
                    state["done"] = True

        def try_c(a, record):
            wx, wy, mvx, mvy = self.carry_velocity(k, a, bx, by)
            dvx, dvy = wx - bvx, wy - bvy
            dv = math.hypot(dvx, dvy)
            if dv > KICK or dv < 1e-6:
                return
            nx, ny = after_move(k, mvx, mvy)
            if kmove is None and (nx - bx) ** 2 + (ny - by) ** 2 > (KR - 0.05) ** 2:
                return
            v = self.evaluate(k, mine, theirs, bx, by, wx, wy)
            if record:
                scored.append((v, "c", a, 0.0))
            act = (dvx / dv, dvy / dv, dv / KICK, None, None, (mvx, mvy))
            if self._rec is not None:
                recs.append((v, self._rec, act))
            if v > state["bestv"]:
                state["bestv"] = v
                state["best"] = act

        # Pass 1: a coarse spread of every kind of kick.
        ns = int(pp["shot_n"])
        for si in range(ns):
            if over():
                break
            gy = -6.0 + 12.0 * si / (ns - 1) if ns > 1 else 0.0
            dx, dy = XL - bx, gy - by
            d = math.hypot(dx, dy)
            try_t(dx / d, dy / d, BALL_CAP, False)
        nc = int(pp["c_carry_n"])
        for i in range(nc):
            if over():
                break
            a = i * 2.0 * math.pi / nc
            try_c(a, True)
        for m in mine:
            if m.id == k.id or over():
                continue
            for lead in pp["c_leads"]:
                tx = m.x + m.vx * lead
                ty = m.y + m.vy * lead
                dx, dy = tx - bx, ty - by
                d = math.hypot(dx, dy)
                if d < 3:
                    continue
                for vend in pp["c_vends"]:
                    if over():
                        break
                    try_t(dx / d, dy / d, vend + d / ROLL, True)
            gx, gy = XL - m.x, -m.y * 0.5
            gl = math.hypot(gx, gy) or 1.0
            for ahead in pp["c_through"]:
                tx = m.x + gx / gl * ahead
                ty = m.y + gy / gl * ahead
                dx, dy = tx - bx, ty - by
                d = math.hypot(dx, dy)
                if d < 4 or over():
                    continue
                try_t(dx / d, dy / d, 4.0 + d / ROLL, True)
        for c, s2 in fan(int(pp["c_drib_n"])):
            for sp in pp["c_drib_speeds"]:
                if over():
                    break
                try_t(c, s2, sp, True)
        for c, s2 in fan(int(pp["c_clear_n"])):
            if over():
                break
            try_t(c, s2, BALL_CAP, True)
        # Pass 2: refine around the best few.
        scored.sort(key=lambda e: -e[0])
        da = pp["refine_da"]
        dc = pp["refine_dc"]
        for v0, kind, a, sp in scored[:int(pp["refine_k"])]:
            if kind == "c":
                for aa in (a - dc, a + dc):
                    if over():
                        break
                    try_c(aa, False)
            else:
                for aa, ss in ((a - da, sp), (a + da, sp), (a, sp * 0.7), (a, min(sp * 1.35, BALL_CAP))):
                    if over():
                        break
                    try_t(math.cos(aa), math.sin(aa), ss, False)
        if pp["la_k"] > 0 and not state["done"]:
            recs.sort(key=lambda e: -e[0])
            seen = 0
            for v, rec, act in recs:
                if seen >= pp["la_k"] or over():
                    break
                q, mpt, mt, vix, viy = rec
                if mpt[0] < pp["la_x"]:
                    continue
                seen += 1
                sv = self.shot_value_from(theirs, mpt[0], mpt[1], mt, vix, viy)
                keep = max(self.pos_value(*mpt), pp["la_w"] * sv)
                v2 = q * keep + (1 - q) * self.lose_value(*mpt)
                if v2 > state["bestv"]:
                    state["bestv"] = v2
                    state["best"] = act
        best = state["best"]
        if best is None:
            return PlayerAction(movement=kmove or (0.0, 0.0), kick_direction=(1.0, 0.0), kick_power=1.0)
        kx, ky, pw, ux, uy, cmove = best
        if cmove is not None:
            return PlayerAction(movement=kmove or cmove, kick_direction=(kx, ky), kick_power=pw)
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
