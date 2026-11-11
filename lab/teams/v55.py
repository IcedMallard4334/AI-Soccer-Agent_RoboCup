"""v55: v54 plus switchable experiments: keeper-aware shot range (C3)
and a carrier model for the chaser (D1).

v54: v53 with a keeper-spot table and off-ball plan re-use between
ticks where nothing has changed.

v53: v51, faster (same decisions): no dead support scoring, pitch
control with one arrival lookup per spot, interception scans limited to
beating the best so far, keeper spot directions computed once.

v51: v50 + per-match calibration of the learned keep model: compare its
predictions on our own kicks with what happens, and shift its risk level
to fit this opponent.

v50: v49 with pitch control using a closed-form arrival estimate (coasting
point + inverse distance table) instead of the iterative reach search.

v49: v48 with the safe-dribble checks made cheap (distance bound before the
exact reach) and its shot lookahead inside the time budget.

v48: v47 with the keep model re-fitted on v47's own play (one round of
policy iteration).

v46: v45 with keep and goal probabilities from logistic models fitted on
40,000 logged kicks (the hand-set curves were badly miscalibrated).

v45: v41 with the keep and goal probabilities behind keep_prob/goal_prob
(same formulas by default) and optional logging of each chosen kick's
features and outcome, with exploration, to learn those models from data.

v41: v40 + shot-setting dribbles: in the final third the best safe dribble
headings are also scored by the 30 u/s first-time strike they set up.

v40: v39 + safe-dribble possession engine: the carrier checks 12 headings
for a touch no defender can reach before the next touch and keeps the ball
at his feet unless a pass or shot is clearly better.

v39: v38 + possession bias: controlled carry touches get a bonus over firm
kicks into space (keep the ball at feet like the top ladder teams).

v38: v37 with the dominance mode tuned on the mid-table proxy: triggers at
50% territory, shoots with goal_bias 0 from up to 42 units, box presence on.

v37: v36 + box presence: in dominance mode one supporter attacks the far
side of the box (cut-backs, rebounds) whenever the ball is in their half.

v36: v34 + dominance mode: when we have held most of the territory for a
while and are not clearly winning, shoot far more readily and from further
out (mid-table teams let us dominate, then hold out for 0-0).

v32fast: v32 with a faster kick search and identical decisions: straight
and one-bounce ball paths in closed form with the interception scan inlined
in evaluate, per-reach threshold tables, repeated kicks evaluated once.

v32: v31 with the search order matched to what actually wins: firm kicks
into space (dribbles) first, then passes and shots, refine early, carries late.

v31: v29 with refinement moved early (a compact first pass, refine the best
three, then the rest and refine again), because the chosen kick usually comes
from refinement and a slow server never reached it.

v29: v28 with an anytime kick search: the most valuable candidates first
(passes, forward carries), shots only within range, so a cut-short search on
a slow machine still finds good kicks.

v28: v26 with lazy straight ball paths (positions computed only at the
ticks the interception scan actually looks at).

v26: v25 with a much faster kick evaluator (tight scan loop over
pre-extracted player tuples, table-based fallback), so the full search fits
the slower server's time budget.

v25: v24 + time guard on pitch-control recomputation (reuse the cached
spots when this tick has already spent its budget), for a slower server.

v24: v23 + cut-back defence: the keeper stays home and a defender guards
the cut-back spot when the ball is wide in our third (how the top ladder
teams scored against v23).

v23: v22 + deep-block detection: against a parked bus, shoot more readily.

v22: v21 made lean: pitch-control targets cached for a few ticks and
anticipation skipped when the tick's time budget is mostly spent.

v21: v20 + pitch-control support positions (spots a team-mate reaches
before any defender once the pass arrives, weighted by learned value).

v20: v19 with tuned parameters + game-state management (chase the game
when level or behind late, protect a late lead).

v19: v18 + optional two-step shot lookahead and opponent kick cooldowns in
the kick evaluator.

v18: v17 + anticipation: predict the opponent's next kick with our own
evaluator (from their side) and send our best interceptor to cut it off.

v17: v16 with the value of opponent possession capped (a ball handed to
their keeper is never good for us).

v16: v14 with a learned possession value (expected threat measured from
300 evenly matched games) in place of the hand-made position/loss values.

v14: v13 with a coarse-to-fine kick search (fewer evaluations, refined
around the best options).

v13: v12 with a faster evaluator (closed-form wall bounce, interceptors
checked most-likely first so the rest are pruned).

v12: v11 with a configurable (and slimmer) kick candidate set.

v11: v10 with tuned shape (open supporters, deeper cover, less raw progress);
second presser and contested-kick penalty off (they did not help).

v10: v9 + second presser in our half + contested-kick handling.

v9: v8 without the xG term (it made the team passive against massed defences).

v8: v7 + carry touches (ball placed just ahead of the runner).

v7: v6 + expected-goals map in the position value.

v6: exact player motion model, velocity controller, post-move kick reach,
restart tracking, optimised keeper, pitch-control support, lane defence."""

import math
import random
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
    "budget": 0.006,
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
    "pc_every": 6,
    "pc_move": 6.0,
    "guard": 0.6,
    "bus_x": 36.0,
    "bus_n": 2.5,
    "bus_ema": 0.01,
    "bus_mode": {"goal_bias": 0.0},
    "dom_ema": 0.004,
    "dom_on": 0.5,
    "carry_bonus": 0.0,
    "sd_on": 1,
    "sd_n": 12,
    "sd_safe": 2.0,
    "sd_bonus": 0.3,
    "sd_r": 2.2,
    "sd_xmin": 15.0,
    "sd_fwd": 0.05,
    "sd_shot_x": 18.0,
    "sd_shot_k": 3,
    "sd_shot_w": 0.85,
    "log_on": 0,
    "log_eps": 0.15,
    "learned": 1,
    "learned_keep": 1,
    "learned_goal": 0,
    "kc_on": 1,
    "shot_kd": 0.0,
    "shot_r0": 24.0,
    "carrier": 0,
    "car_t": 3.0,
    "car_off": 1.5,
    "gk_table": 1,
    "reuse_k": 3,
    "kc_prior": 30.0,
    "kc_gain": 1.0,
    "kc_max": 1.5,
    "carry_first": 0,
    "dom_lead": 1,
    "dom_mode": {"goal_bias": 0.0, "shot_range": 42.0, "box_on": 1},
    "box_on": 0,
    "box_x": 42.0,
    "box_y": 5.0,
    "wide_x": -30.0,
    "wide_y": 9.0,
    "home_x": -48.0,
    "home_y": 0.12,
    "home_cap": 3.5,
    "box_guard": 1,
    "pc_late": 0.5,
    "shot_range": 32.0,
    "shot_n1": 5,
    "max_evals": 32,
    "guard_x": -40.0,
    "guard_y": 0.15,
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
G3 = DT * (1 - F ** 3) / (1 - F)
F5 = F ** 5


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


# Logistic models fitted on logged kicks (lab/fit.py): chance we keep the
# ball after a kick, and chance a shot scores.
KEEP_W = [1.82138, 0.63463, 0.04155, 0.20122, -0.42421, 0.07464, -0.74373]
GOAL_W = [-1.05645, 1.76979, 0.19097, -0.33454, 0.28692, -1.37107]


def clampf(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ball_path(px, py, vx, vy, n,
              DT=DT, F=F, XL=XL, XM=XM, YM=YM, GH=GH, WALL_E=WALL_E):
    """Exact free-ball prediction for ticks 1..n: (points, goal_tick, side)."""
    pts = []
    add = pts.append
    for t in range(1, n + 1):
        px += vx * DT
        py += vy * DT
        vx *= F
        vy *= F
        if -YM <= py <= YM and -XM <= px <= XM:
            # Inside the walls: no bounce and no goal.
            add((px, py))
            if vx * vx + vy * vy < 0.01:
                break
            continue
        if py > YM:
            py = 2 * YM - py
            vy = -vy * WALL_E
        elif py < -YM:
            py = -2 * YM - py
            vy = -vy * WALL_E
        if -GH <= py <= GH:
            if px > XL:
                add((px, py))
                return pts, t, 1
            if px < -XL:
                add((px, py))
                return pts, t, -1
        else:
            if px > XM:
                px = 2 * XM - px
                vx = -vx * WALL_E
            elif px < -XM:
                px = -2 * XM - px
                vx = -vx * WALL_E
        add((px, py))
        if vx * vx + vy * vy < 0.01:
            break
    return pts, None, 0


GT = [DT * (1 - F ** t) / (1 - F) for t in range(1, HORIZON + 1)]
FPOW = [F ** t for t in range(HORIZON + 2)]
GEND = GT[-1]


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


def reach_est(px, py, vx, vy, qx, qy, r, A=0.45):
    """Quick arrival estimate for positioning: distance from the player's
    coasting point, turned into ticks with the from-rest distance table."""
    d = math.sqrt((qx - px - vx * A) ** 2 + (qy - py - vy * A) ** 2) - r
    if d <= 0.0:
        return 0
    return bisect_left(DREST, d)


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


def _first(e):
    return e[0]


def as_tuples(group):
    return [(b.x, b.y, b.vx, b.vy, b.drift, b.id, b.cd) for b in group]


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


def scan(x, y, vx, vy, pts, r, start, lim, delay, step,
         SPD=SPD, AD=AD, DREST=DREST, FPOW=FPOW, sqrt=math.sqrt, NMAX=NMAX):
    """first_intercept for a player given as numbers: earliest 1-based tick
    < lim (None: no limit) at which (x, y, vx, vy) can be within r of pts.
    Returns (t, qx, qy) or None."""
    n = len(pts)
    capped = lim is not None and lim <= n
    if capped:
        n = int(lim) - 1
    i = start
    while i < n:
        t = i + 1 - delay
        qx, qy = pts[i]
        dx = qx - x
        dy = qy - y
        if t >= 0:
            if t > NMAX:
                t = NMAX
            R = r + SPD[t]
            d2 = dx * dx + dy * dy
            if d2 <= R * R:
                a = AD[t]
                ex = dx - vx * a
                ey = dy - vy * a
                R2 = r + DREST[t]
                e2 = ex * ex + ey * ey
                if e2 <= R2 * R2:
                    return i + 1, qx, qy
                gap = sqrt(e2) - R2
            else:
                gap = sqrt(d2) - R
        else:
            gap = sqrt(dx * dx + dy * dy) - r
        k = int(gap / (step * FPOW[i] + 0.45))
        i += k if k > 1 else 1
    if capped or not pts:
        return None
    qx, qy = pts[-1]
    # Resting ball: time to cover the distance beyond the coasting point.
    a = AD[NMAX]
    d = sqrt((qx - x - vx * a) ** 2 + (qy - y - vy * a) ** 2) - r
    t = rest_ticks(d) + delay
    if t < len(pts):
        t = len(pts)
    if lim is None or t < lim:
        return t, qx, qy
    return None


_TABS = {}
_GK = {}


def scan_tables(r):
    """scan()'s per-tick reach thresholds for reach r and no delay, indexed
    by i (tick i+1): (r+SPD)^2, r+SPD, AD, (r+DREST)^2, r+DREST."""
    tab = _TABS.get(r)
    if tab is None:
        r1 = [r + SPD[i + 1] for i in range(HORIZON)]
        r2 = [r + DREST[i + 1] for i in range(HORIZON)]
        tab = ([R * R for R in r1], r1, AD[1:HORIZON + 1], [R * R for R in r2], r2)
        _TABS[r] = tab
    return tab


def line_path(bx, by, vx, vy):
    """The free ball's path in closed form, without building the points:
    (ib, kb) when the ball meets no end wall and at most one side wall within
    HORIZON ticks, else None (use ball_path). The position at tick i+1
    is (bx + vx*GT[i], y) with y = by + vy*GT[i], or kb - WALL_E*y from
    index ib on (ib = HORIZON: a straight path)."""
    ex = bx + vx * GEND
    ey = by + vy * GEND
    if not -XM <= ex <= XM:
        return None
    if -YM <= ey <= YM:
        return HORIZON, 0.0
    lim = YM if ey > 0 else -YM
    g_hit = (lim - by) / vy
    i = bisect_left(GT, g_hit)
    if i >= HORIZON:
        return None
    yr = by + vy * GT[i]
    k = 2.0 * lim - yr + WALL_E * yr
    # Both pieces are monotonic, so their ends bound them.
    ends = [k - WALL_E * yr, k - WALL_E * ey]
    if i > 0:
        ends.append(by + vy * GT[0])
        ends.append(by + vy * GT[i - 1])
    if max(ends) <= YM and min(ends) >= -YM:
        return i, k
    return None


def line_points(bx, by, vx, vy, ib, kb):
    """The list of points of a line_path."""
    return [(bx + vx * g, by + vy * g if i < ib else kb - WALL_E * (by + vy * g))
            for i, g in enumerate(GT)]


def scan_pts(x, y, vx, vy, pts, r, start, lim, step, tab,
             FPOW=FPOW, sqrt=math.sqrt):
    """scan() with no delay; tab = scan_tables(r)."""
    RR, R1, A1, QQ, R2 = tab
    n = len(pts)
    capped = lim is not None and lim <= n
    if capped:
        n = int(lim) - 1
    i = start
    while i < n:
        qx, qy = pts[i]
        dx = qx - x
        dy = qy - y
        d2 = dx * dx + dy * dy
        if d2 <= RR[i]:
            a = A1[i]
            ex = dx - vx * a
            ey = dy - vy * a
            e2 = ex * ex + ey * ey
            if e2 <= QQ[i]:
                return i + 1, qx, qy
            gap = sqrt(e2) - R2[i]
        else:
            gap = sqrt(d2) - R1[i]
        q = gap / (step * FPOW[i] + 0.45)
        i += 1 if q < 2.0 else int(q)
    if capped or not pts:
        return None
    qx, qy = pts[-1]
    a = AD[NMAX]
    d = sqrt((qx - x - vx * a) ** 2 + (qy - y - vy * a) ** 2) - r
    t = rest_ticks(d)
    if t < len(pts):
        t = len(pts)
    if lim is None or t < lim:
        return t, qx, qy
    return None


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
    name = "v55"
    version = "55"

    def __init__(self):
        self.p = dict(P)
        self.base_p = self.p
        self._reset_state()

    def _reset_state(self):
        self.kc_shift = 0.0
        self.kc_n = 0.0
        self.kc_pred = 0.0
        self.kc_act = 0.0
        self.kc_pending = None
        self.rng = random.Random(7)
        self.chosen_feat = None
        self._feat = None
        self.log_rows = []
        self.log_pending = None
        self.pc_cache = None
        self.deep = 0.0
        self.terr = 0.5
        if not hasattr(self, "xg"):
            self.xg = None
        self.chaser_id = None
        self.sup_cache = None
        self.sup_tick = -100
        self.restart = None      # (start_tick, kicking_team, length)
        self.plan_cache = None   # (tick, ball points, their_kickoff, targets)
        self.gk_depth = 0.0      # their keeper's distance off his line
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
    def keep_base(self, f):
        """The learned keep probability without this match's shift."""
        _, margin, mt, sp, rx, free = f
        m = max(-15.0, min(15.0, margin)) / 10.0
        s2 = sp / 20.0
        w = KEEP_W
        z = (w[0] + w[1] * m + w[2] * free + w[3] * min(mt, 80.0) / 20.0
             + w[4] * s2 + w[5] * rx / 50.0 + w[6] * m * s2)
        return 1.0 / (1.0 + math.exp(-z))

    def kc_events(self, obs):
        pend = self.kc_pending
        if pend is None:
            return
        for ev in obs.events:
            k = ev.get("kind")
            if k == "goal":
                self.kc_pending = None
                return
            if k == "kick" and ev.get("tick", obs.tick) > pend[0]:
                self.kc_pending = None
                self.kc_record(pend[1], 1.0 if ev.get("team") == 0 else 0.0)
                return
        if obs.tick - pend[0] > 150:
            self.kc_pending = None

    def kc_record(self, pred, kept):
        bp = self.base_p
        self.kc_n += 1.0
        self.kc_pred += pred
        self.kc_act += kept
        n0 = bp["kc_prior"]
        pr = (self.kc_pred + n0 * 0.87) / (self.kc_n + n0)
        ac = (self.kc_act + n0 * 0.87) / (self.kc_n + n0)
        pr = min(max(pr, 0.02), 0.98)
        ac = min(max(ac, 0.02), 0.98)
        adj = (math.log(ac / (1 - ac)) - math.log(pr / (1 - pr))) * bp["kc_gain"]
        m = bp["kc_max"]
        self.kc_shift = max(-m, min(m, adj))

    def log_events(self, obs):
        pend = self.log_pending
        if pend is None:
            return
        for ev in obs.events:
            k = ev.get("kind")
            if k == "goal":
                self.log_close(1.0 if ev.get("team") == 0 else 0.0, True)
                return
            if k == "kick" and ev.get("tick", obs.tick) > pend[0]:
                self.log_close(1.0 if ev.get("team") == 0 else 0.0, False)
                return
        if obs.tick - pend[0] > 150:
            self.log_close(0.0, False)

    def log_close(self, ours, goal):
        tick, feat = self.log_pending
        self.log_pending = None
        if feat[0] == "k":
            self.log_rows.append(feat + (ours,))
        else:
            self.log_rows.append(feat + ((1.0 if (goal and ours) else 0.0),))

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
        if bp["log_on"]:
            self.log_events(obs)
        if bp["kc_on"]:
            self.kc_events(obs)
        deep = 0
        for q in obs.opponents[1:]:
            if q.position[0] > bp["bus_x"]:
                deep += 1
        self.deep = self.deep + (deep - self.deep) * bp["bus_ema"]
        bx0 = obs.ball.position[0]
        self.terr += ((1.0 if bx0 > 0.0 else 0.0) - self.terr) * bp["dom_ema"]
        sg, so = obs.score
        if self.terr >= bp["dom_on"] and sg - so <= bp["dom_lead"]:
            self.p = dict(self.p)
            self.p.update(bp["dom_mode"])
        if self.deep >= bp["bus_n"]:
            self.p = dict(self.p)
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
        self.gk_depth = XL - theirs[0].x
        actions = TeamAction()
        tick = obs.tick
        self.update_restart(obs)
        their_kickoff = self.restart is not None and self.restart[1] == 1
        if bp["reuse_k"] > 1:
            got = self.reuse_plan(obs, mine, bx, by, tick, their_kickoff)
            if got is not None:
                return got
        self.plan_cache = None
        tg = []
        kicked = False

        pts, gtick, gside = ball_path(bx, by, bvx, bvy, HORIZON)
        if not pts:
            pts = [(bx, by)]
        bstep = math.hypot(bvx, bvy) * DT + 0.05

        r = p["r_get"]
        # Only the earliest interception of each side is used (and the
        # chaser's): each scan only has to beat the best found so far.
        opp_ic = {}
        opp_best = 1e9
        opp_first = None
        for b in theirs:
            got = first_intercept(b, pts, r, 0, None if opp_first is None else opp_best, step=bstep)
            opp_ic[b.id] = got
            t = got[0]
            if t is not None and t < opp_best:
                opp_best = t
                opp_first = b

        my_ic = {}
        field_players = mine[1:]
        chaser = None
        best = 1e9
        hyst = p["hyst"]
        for b in field_players:
            h = hyst if b.id == self.chaser_id else 0.0
            got = first_intercept(b, pts, r, 0, None if chaser is None else best + h, step=bstep)
            my_ic[b.id] = got
            t = got[0]
            if t is None:
                continue
            if h:
                t -= h
            if t < best:
                best = t
                chaser = b
        keeper = mine[0]
        my_ic[0] = first_intercept(keeper, pts, r, 0, None if chaser is None else best, step=bstep)
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
                kicked = True
                self.chosen_feat = None
                actions.set(kicker.id, self.choose_kick(kicker, kmove, mine, theirs,
                                                        bx, by, bvx, bvy))
                used.add(kicker.id)
                if p["kc_on"]:
                    if self.kc_pending is not None and self.kc_pending[0] < tick:
                        self.kc_record(self.kc_pending[1], 1.0)
                    f = self.chosen_feat
                    if f is not None and f[0] == "k":
                        self.kc_pending = (tick, self.keep_base(f))
                if p["log_on"]:
                    if self.log_pending is not None and self.log_pending[0] < tick:
                        self.log_close(1.0, False)
                    if self.chosen_feat is not None:
                        self.log_pending = (tick, self.chosen_feat)

        if chaser is not None and chaser.id not in used and not their_kickoff:
            _, ix, iy = my_ic[chaser.id]
            if ix is None:
                ix, iy = bx, by
            tx, ty = self.approach_point(chaser, ix, iy)
            if (p["carrier"] and not attacking and opp_first is not None
                    and opp_best <= p["car_t"]):
                tx, ty = self.carrier_point(chaser, opp_first)
            actions.set(chaser.id, PlayerAction(movement=drive(chaser, tx, ty, 100.0)))
            tg.append((chaser.id, tx, ty, 100.0))
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
                tg.append((b.id, tx, ty, 100.0))
                used.add(b.id)
                rest = [q for q in rest if q.id != b.id]
        if (not attacking and not their_kickoff and opp_first is not None
                and opp_ic[opp_first.id][1] is not None
                and opp_ic[opp_first.id][1] < p["press2_x"] and len(rest) >= 3):
            hx, hy = opp_ic[opp_first.id][1], opp_ic[opp_first.id][2]
            cand = None
            ct = 1e9
            for b in rest:
                t = first_intercept(b, pts, r, step=bstep)[0]
                if t is not None and t < ct:
                    ct, cand = t, b
            if cand is not None and ct - opp_best < p["press2_gap"]:
                # Come from the goal side of where they will receive it.
                gx, gy = -XL - hx, -hy
                gl = math.hypot(gx, gy) or 1.0
                tx, ty = hx + gx / gl * 1.5, hy + gy / gl * 1.5
                actions.set(cand.id, PlayerAction(movement=drive(cand, tx, ty, 100.0)))
                tg.append((cand.id, tx, ty, 100.0))
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
            tg.append((b.id, tx, ty, gain))
        if not kicked and gside != -1 and len(tg) == len(mine) - 1:
            self.plan_cache = (tick, pts, their_kickoff, tg)
        if their_kickoff:
            self.keep_out(actions, mine)
        return actions

    def reuse_plan(self, obs, mine, bx, by, tick, their_kickoff):
        """Last full tick's targets, if nothing has happened since that it
        did not predict; else None."""
        c = self.plan_cache
        if c is None:
            return None
        t0, pts, kickoff, targets = c
        j = tick - t0
        if j <= 0 or j >= self.base_p["reuse_k"] or j > len(pts) or kickoff != their_kickoff:
            return None
        ex, ey = pts[j - 1]
        if abs(ex - bx) > 0.05 or abs(ey - by) > 0.05:
            return None
        for ev in obs.events:
            if ev.get("kind") in ("kick", "goal", "turnover", "foul"):
                return None
        lim = (KR - 0.05) ** 2
        for b in mine:
            if b.cd > 0:
                continue
            if obs.can_kick(b.id):
                return None
            mx, my = drive(b, bx, by, 100.0)
            nx, ny = after_move(b, mx, my)
            if (nx - bx) ** 2 + (ny - by) ** 2 <= lim:
                return None
        actions = TeamAction()
        for pid, tx, ty, gain in targets:
            actions.set(pid, PlayerAction(movement=drive(mine[pid], tx, ty, gain)))
        actions.set(0, PlayerAction(movement=self.keeper_move(mine[0], bx, by, pts, None, 0)))
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

    def carrier_point(self, b, o):
        """Where carrier o will be when b can get there (o keeps his
        velocity), moved car_off towards our goal."""
        x, y = o.x, o.y
        for _ in range(3):
            t = reach_est(b.x, b.y, b.vx, b.vy, x, y, 0.0)
            x = clampf(o.x + o.vx * DT * t, -PXM, PXM)
            y = clampf(o.y + o.vy * DT * t, -PYM, PYM)
        gx, gy = -XL - x, -y
        gl = math.hypot(gx, gy) or 1.0
        off = self.p["car_off"]
        return x + gx / gl * off, y + gy / gl * off

    @staticmethod
    def approach_point(b, ix, iy):
        dx, dy = XL - ix, -iy
        d = math.hypot(dx, dy) or 1.0
        if math.hypot(b.x - ix, b.y - iy) > 6:
            return ix, iy
        return ix - dx / d * 0.8, iy - dy / d * 0.8

    # ------------------------------------------------------------------
    def keeper_spot(self, tx, ty):
        """keeper_spot_exact, interpolated from a 1-unit grid filled lazily
        (the spot is symmetric in y)."""
        if not self.p["gk_table"]:
            return self.keeper_spot_exact(tx, ty)
        sgn = 1.0
        if ty < 0.0:
            ty = -ty
            sgn = -1.0
        fx = clampf(tx, -50.0, 50.0) + 50.0
        fy = ty if ty < 30.0 else 30.0
        i = int(fx)
        j = int(fy)
        if i > 99:
            i = 99
        if j > 29:
            j = 29
        ax = fx - i
        ay = fy - j
        tab = _GK
        c = []
        for key in ((i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)):
            v = tab.get(key)
            if v is None:
                v = tab[key] = self.keeper_spot_exact(key[0] - 50.0, float(key[1]))
            c.append(v)
        w00 = (1 - ax) * (1 - ay)
        w10 = ax * (1 - ay)
        w01 = (1 - ax) * ay
        w11 = ax * ay
        kx = c[0][0] * w00 + c[1][0] * w10 + c[2][0] * w01 + c[3][0] * w11
        ky = c[0][1] * w00 + c[1][1] * w10 + c[2][1] * w01 + c[3][1] * w11
        return kx, ky * sgn

    def keeper_spot_exact(self, tx, ty):
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
        dirs = []
        for gx, gy in ((-XL, GH - 0.6), (-XL, -GH + 0.6)):
            lx, ly = gx - tx, gy - ty
            ll = math.hypot(lx, ly) or 1.0
            dirs.append((lx / ll, ly / ll))
        gk_r = p["gk_r"]
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
            for lx, ly in dirs:
                along = (kx - tx) * lx + (ky - ty) * ly
                h = abs((kx - tx) * ly - (ky - ty) * lx)
                tb = ball_ticks(max(along, 0.0), sp)
                tk = rest_ticks(h - gk_r) + 1.0
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
        p = self.p
        if tx < p["wide_x"] and abs(ty) > p["wide_y"]:
            # Ball wide in our third: the danger is the ball across the box,
            # not a shot from the angle - stay home, near the middle.
            cap = p["home_cap"]
            return drive(k, p["home_x"], clampf(ty * p["home_y"], -cap, cap), 3.0)
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
        if p["box_on"] and hx > 5.0 and len(free) >= 2:
            # Someone in the box, far side from the ball.
            bxs = p["box_x"]
            bys = -p["box_y"] if hy > 0 else p["box_y"]
            g = min(free, key=lambda q: (q.x - bxs) ** 2 + (q.y - bys) ** 2)
            free.remove(g)
            out.append((g, (bxs, bys)))
        if not p["pc"] and (self.sup_cache is None or tick - self.sup_tick >= p["sup_every"]):
            self.sup_cache = self.score_spots(theirs, hx, hy)
            self.sup_tick = tick
        if p["pc"]:
            ids = tuple(b.id for b in free)
            c = self.pc_cache
            late = time.perf_counter() - self.t0 > p["budget"] * p["pc_late"]
            if (c is not None and c[0] == ids
                    and (late or (tick - c[1] < p["pc_every"]
                                  and abs(c[2] - hx) + abs(c[3] - hy) < p["pc_move"]))):
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
        lane_w = p["pc_lane"]
        delay = p["pc_delay"]
        sqrt = math.sqrt
        exp = math.exp
        log = math.log
        opp = [(o.x, o.y, o.vx * 0.45, o.vy * 0.45) for o in theirs]
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
                q = 1.0 - L / (ROLL * (8.0 + L / ROLL))
                tb = (log(q) / LNF if q > 0.0 else 999.0) + delay
                dmin = 1e18
                lane = 10.0
                ux, uy = dx / L, dy / L
                for ox0, oy0, ax, ay in opp:
                    ex = sx - ox0 - ax
                    ey = sy - oy0 - ay
                    d2 = ex * ex + ey * ey
                    if d2 < dmin:
                        dmin = d2
                    ox, oy = ox0 - hx, oy0 - hy
                    u = ox * ux + oy * uy
                    if 0.0 < u < L:
                        m = abs(ox * uy - oy * ux) - (1.5 + 0.22 * u)
                        if m < lane:
                            lane = m
                tthem = bisect_left(DREST, sqrt(dmin) - r)
                spots.append((sx, sy, tb, tthem, self.pos_value(sx, sy) + lane_w * clampf(lane, -5.0, 5.0)))
        out = []
        chosen = []
        for b in free:
            bestv = -1e9
            bests = (b.x, b.y)
            bx0, by0 = b.x, b.y
            ax, ay = b.vx * 0.45, b.vy * 0.45
            for sx, sy, tb, tthem, v0 in spots:
                ok = True
                for cx, cy in chosen:
                    if (cx - sx) ** 2 + (cy - sy) ** 2 < 100.0:
                        ok = False
                        break
                if not ok:
                    continue
                ex = sx - bx0 - ax
                ey = sy - by0 - ay
                tus = bisect_left(DREST, sqrt(ex * ex + ey * ey) - r)
                arrive = tb if tb > tus else tus
                z = (tthem - arrive) / sig
                if z > 30.0:
                    z = 30.0
                elif z < -30.0:
                    z = -30.0
                v = v0 / (1.0 + exp(-z))
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
        if p["box_guard"] and hx < p["wide_x"] and abs(hy) > p["wide_y"]:
            # Guard the cut-back spot in front of goal.
            targets.append((p["guard_x"], -hy * p["guard_y"]))
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

    def evaluate(self, kicker, mine, theirs, bx, by, vx, vy,
                 GT=GT, FPOW=FPOW, HORIZON=HORIZON, WALL_E=WALL_E, sqrt=math.sqrt):
        p = self.p
        self._rec = None
        lp = line_path(bx, by, vx, vy)
        if lp is None:
            pts, gt, gs = ball_path(bx, by, vx, vy, HORIZON)
            return self.evaluate_pts(kicker, bx, by, vx, vy, pts, gt, gs, False)
        ib, kb = lp
        if p["react"]:
            return self.evaluate_pts(kicker, bx, by, vx, vy, line_points(bx, by, vx, vy, ib, kb),
                                     None, 0, ib == HORIZON)
        # The ball's path is a line (with at most one side-wall bounce):
        # positions are computed only where the scans look.
        sp = math.hypot(vx, vy)
        step = sp * DT + 0.05
        r = p["r_get"]
        tab = _TABS.get(r) or scan_tables(r)
        theirs_t = self._theirs_t
        mine_t = self._mine_t
        if ib == HORIZON and sp > 1e-6:
            # Lower bound on each player's intercept tick from his distance to
            # the ball's line; check the likeliest first, prune the rest.
            ux, uy = vx / sp, vy / sp
            L = sp * GEND
            ex = bx + vx * GEND
            ey = by + vy * GEND
            olist = []
            j = 0
            for pt in theirs_t:
                rx = pt[0] - bx
                ry = pt[1] - by
                a = rx * ux + ry * uy
                if a <= 0.0:
                    dmin = sqrt(rx * rx + ry * ry)
                elif a >= L:
                    dmin = sqrt((pt[0] - ex) ** 2 + (pt[1] - ey) ** 2)
                else:
                    dmin = abs(rx * uy - ry * ux)
                olist.append(((dmin - r - pt[4]) * 2.5, j, pt))
                j += 1
            olist.sort()
            mlist = []
            j = 0
            for pt in mine_t:
                rx = pt[0] - bx
                ry = pt[1] - by
                a = rx * ux + ry * uy
                if a <= 0.0:
                    dmin = sqrt(rx * rx + ry * ry)
                elif a >= L:
                    dmin = sqrt((pt[0] - ex) ** 2 + (pt[1] - ey) ** 2)
                else:
                    dmin = abs(rx * uy - ry * ux)
                mlist.append(((dmin - r - pt[4]) * 2.5, j, pt))
                j += 1
            mlist.sort()
        else:
            olist = [(-1e9, 0, pt) for pt in theirs_t]
            mlist = [(-1e9, 0, pt) for pt in mine_t]
        # The interception scan (as scan(), no delay, inlined): their
        # players first, then ours, each limited to beat the earliest tick
        # found so far.
        RR, R1, A1, QQ, R2 = tab
        usecd = p["use_cd"]
        kid = kicker.id
        tail = None
        lim = None
        hit = None
        for lst in (olist, mlist):
            mine_side = lst is mlist
            if mine_side:
                ot, opt = lim, hit
                hit = None
            for lb, _, pl in lst:
                if lim is not None and lb >= lim:
                    break
                x, y, pvx, pvy = pl[0], pl[1], pl[2], pl[3]
                if mine_side:
                    i = 5 if pl[5] == kid else 0
                else:
                    i = pl[6] if usecd else 0
                capped = lim is not None and lim <= HORIZON
                n = int(lim) - 1 if capped else HORIZON
                while i < n:
                    g = GT[i]
                    qx = bx + vx * g
                    qy = by + vy * g
                    if i >= ib:
                        qy = kb - WALL_E * qy
                    dx = qx - x
                    dy = qy - y
                    d2 = dx * dx + dy * dy
                    if d2 <= RR[i]:
                        a = A1[i]
                        ex = dx - pvx * a
                        ey = dy - pvy * a
                        e2 = ex * ex + ey * ey
                        if e2 <= QQ[i]:
                            lim = i + 1
                            hit = (qx, qy)
                            break
                        gap = sqrt(e2) - R2[i]
                    else:
                        gap = sqrt(d2) - R1[i]
                    q = gap / (step * FPOW[i] + 0.45)
                    i += 1 if q < 2.0 else int(q)
                else:
                    if capped:
                        continue
                    # Resting ball: time to cover the distance beyond the
                    # coasting point.
                    if tail is None:
                        qx = bx + vx * GEND
                        qy = by + vy * GEND
                        if ib < HORIZON:
                            qy = kb - WALL_E * qy
                        tail = (qx, qy)
                    qx, qy = tail
                    a = AD[NMAX]
                    d = sqrt((qx - x - pvx * a) ** 2 + (qy - y - pvy * a) ** 2) - r
                    t = rest_ticks(d)
                    if t < HORIZON:
                        t = HORIZON
                    if lim is None or t < lim:
                        lim = t
                        hit = (qx, qy)
        mt, mpt = lim, hit
        if mpt is not None:
            margin = (ot - mt) if opt is not None else 30.0
            q = self.keep_prob(margin, mt, math.hypot(vx, vy), mpt[0], opt is None)
            i = int(mt) - 1
            if 1 <= i < HORIZON:
                g0 = GT[i - 1]
                g1 = GT[i]
                y0 = by + vy * g0
                if i - 1 >= ib:
                    y0 = kb - WALL_E * y0
                y1 = by + vy * g1
                if i >= ib:
                    y1 = kb - WALL_E * y1
                vix = ((bx + vx * g1) - (bx + vx * g0)) / DT
                viy = (y1 - y0) / DT
            else:
                vix, viy = vx * 0.5, vy * 0.5
            self._rec = (q, mpt, mt, vix, viy)
            return q * self.pos_value(*mpt) + (1 - q) * self.lose_value(*mpt)
        if opt is not None:
            return self.lose_value(*opt)
        return -1.0

    def evaluate_pts(self, kicker, bx, by, vx, vy, pts, gt, gs, straight):
        """evaluate() over a list of ball positions."""
        p = self.p
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
        theirs_t = self._theirs_t
        mine_t = self._mine_t
        if straight:
            # Lower bound on each player's intercept tick from his distance to
            # the ball's line; check the likeliest first, prune the rest.
            olist = []
            for pt in theirs_t:
                rx = pt[0] - bx
                ry = pt[1] - by
                a = rx * ux + ry * uy
                if a <= 0.0:
                    dmin = math.sqrt(rx * rx + ry * ry)
                elif a >= L:
                    dmin = math.sqrt((pt[0] - ex) ** 2 + (pt[1] - ey) ** 2)
                else:
                    dmin = abs(rx * uy - ry * ux)
                olist.append(((dmin - r - pt[4]) * 2.5, pt))
            olist.sort(key=_first)
            mlist = []
            for pt in mine_t:
                rx = pt[0] - bx
                ry = pt[1] - by
                a = rx * ux + ry * uy
                if a <= 0.0:
                    dmin = math.sqrt(rx * rx + ry * ry)
                elif a >= L:
                    dmin = math.sqrt((pt[0] - ex) ** 2 + (pt[1] - ey) ** 2)
                else:
                    dmin = abs(rx * uy - ry * ux)
                mlist.append(((dmin - r - pt[4]) * 2.5, pt))
            mlist.sort(key=_first)
        else:
            olist = [(-1e9, pt) for pt in theirs_t]
            mlist = [(-1e9, pt) for pt in mine_t]
        ot = lim
        opt = None
        usecd = p["use_cd"]
        tab = _TABS.get(r) or scan_tables(r)
        for lb, o in olist:
            if ot is not None and lb >= ot:
                break
            if react:
                res = scan(o[0], o[1], o[2], o[3], pts, r, o[6] if usecd else 0, ot, react, step)
            else:
                res = scan_pts(o[0], o[1], o[2], o[3], pts, r, o[6] if usecd else 0, ot, step, tab)
            if res is not None:
                ot, opt = res[0], (res[1], res[2])
        if gs == 1:
            gv = p["xt_scale"] * p["goal_units"]
            if opt is None:
                if p["log_on"]:
                    self._feat = ("g", 30.0, gt, math.hypot(vx, vy), bx, by)
                return gv
            margin = ot - gt
            q = self.goal_prob(margin, gt, math.hypot(vx, vy), bx, by)
            return q * gv + (1 - q) * self.lose_value(*opt)
        mt = ot
        mpt = None
        kid = kicker.id
        for lb, m in mlist:
            if mt is not None and lb >= mt:
                break
            res = scan_pts(m[0], m[1], m[2], m[3], pts, r, 5 if m[5] == kid else 0, mt, step, tab)
            if res is not None:
                mt, mpt = res[0], (res[1], res[2])
        if gs == -1 and opt is None and mpt is None:
            return -10.0
        if mpt is not None:
            margin = (ot - mt) if opt is not None else 30.0
            q = self.keep_prob(margin, mt, math.hypot(vx, vy), mpt[0], opt is None)
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
        self._theirs_t = as_tuples(us)
        self._mine_t = as_tuples(them)
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

    def keep_prob(self, margin, mt, sp, rx, free):
        """Chance we keep the ball, given our reception margin over the first
        opponent (ticks), our reception tick, ball speed and reception x."""
        p = self.p
        self._feat = ("k", margin, mt, sp, rx, 1.0 if free else 0.0)
        if p["learned"] and p["learned_keep"]:
            m = margin if margin < 15.0 else 15.0
            if m < -15.0:
                m = -15.0
            m /= 10.0
            s2 = sp / 20.0
            w = KEEP_W
            z = (w[0] + w[1] * m + w[2] * free + w[3] * (mt if mt < 80.0 else 80.0) / 20.0
                 + w[4] * s2 + w[5] * rx / 50.0 + w[6] * m * s2 + self.kc_shift)
            return 1.0 / (1.0 + math.exp(-z))
        return 1.0 / (1.0 + math.exp(-(margin - p["keep_bias"]) / p["sig_keep"]))

    def goal_prob(self, margin, gt, sp, bx, by):
        """Chance a shot scores, given the first opponent's margin over the
        ball reaching the line (ticks), its travel time and speed."""
        p = self.p
        if p["log_on"]:
            self._feat = ("g", margin, gt, sp, bx, by)
        if p["learned"] and p["learned_goal"]:
            m = margin if margin < 15.0 else 15.0
            if m < -15.0:
                m = -15.0
            w = GOAL_W
            z = (w[0] + w[1] * m / 10.0 + w[2] * (gt if gt < 80.0 else 80.0) / 20.0
                 + w[3] * sp / 30.0 + w[4] * math.hypot(XL - bx, by) / 30.0 + w[5] * abs(by) / 30.0
                 - (p["goal_bias"] - 2.846) / p["sig_goal"])
            if z < -30.0:
                return 0.0
            return 1.0 / (1.0 + math.exp(-z))
        return 1.0 / (1.0 + math.exp(-(margin - p["goal_bias"]) / p["sig_goal"]))

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
            if ot > gt and not (p["learned"] and p["learned_goal"]):
                q = 1.0
            else:
                q = self.goal_prob(min(ot - gt, 30.0), gt, s2, px, py)
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
        self._theirs_t = as_tuples(theirs)
        self._mine_t = as_tuples(mine)
        pp = self.p
        budget = pp["budget"]
        t0 = self.t0
        stop_v = pp["xt_scale"] * pp["goal_units"] * pp["shot_stop"]
        best = None
        bestv = -1e9
        done = False
        n_evals = 0   # evaluations asked for (cached ones included)
        max_evals = pp["max_evals"]
        scored = []   # (value, kind, angle, speed) of non-shot candidates
        recs = []     # (value, reception info, action) of kept-ball candidates
        kick_for = self.kick_for
        atan2 = math.atan2
        log_on = pp["log_on"]
        perf = time.perf_counter
        memo = {}     # ball velocity -> (value, reception info)
        feats = {}    # ball velocity -> features of its probability (logging)
        best_feat = None
        pool = []     # (value, action, features) for exploration when logging

        def evaluate(wx, wy):
            nonlocal n_evals
            n_evals += 1
            self._feat = None
            if wx and wy:
                got = memo.get((wx, wy))
                if got is None:
                    got = memo[(wx, wy)] = (self.evaluate(k, mine, theirs, bx, by, wx, wy), self._rec)
                    feats[(wx, wy)] = self._feat
                self._feat = feats.get((wx, wy))
                return got
            return self.evaluate(k, mine, theirs, bx, by, wx, wy), self._rec

        def over():
            nonlocal done
            if done:
                return True
            if perf() - t0 > budget or n_evals >= max_evals:
                done = True
            return done

        def try_t(ux, uy, sp, record):
            nonlocal best, bestv, done, best_feat
            kk = kick_for(bvx, bvy, ux, uy, sp)
            if kk is None:
                return
            kx, ky, pw, s2 = kk
            v, rec = evaluate(ux * s2, uy * s2)
            if record:
                scored.append((v, "t", atan2(uy, ux), sp))
            act = (kx, ky, pw, ux, uy, None)
            if rec is not None:
                recs.append((v, rec, act))
            if log_on and self._feat is not None:
                pool.append((v, act, self._feat))
            if v > bestv:
                bestv = v
                best = act
                best_feat = self._feat
                if v >= stop_v:
                    done = True

        def try_c(a, record):
            nonlocal best, bestv, best_feat
            wx, wy, mvx, mvy = self.carry_velocity(k, a, bx, by)
            dvx, dvy = wx - bvx, wy - bvy
            dv = math.hypot(dvx, dvy)
            if dv > KICK or dv < 1e-6:
                return
            nx, ny = after_move(k, mvx, mvy)
            if kmove is None and (nx - bx) ** 2 + (ny - by) ** 2 > (KR - 0.05) ** 2:
                return
            v, rec = evaluate(wx, wy)
            v += pp["carry_bonus"]
            if record:
                scored.append((v, "c", a, 0.0))
            act = (dvx / dv, dvy / dv, dv / KICK, None, None, (mvx, mvy))
            if rec is not None:
                recs.append((v, rec, act))
            if log_on and self._feat is not None:
                pool.append((v, act, self._feat))
            if v > bestv:
                bestv = v
                best = act
                best_feat = self._feat

        # Safe dribble: keep the ball at feet along the heading where no
        # defender can get to it before our next touch (5 ticks).
        if pp["sd_on"] and bx > pp["sd_xmin"]:
            sd_n = int(pp["sd_n"])
            sd_safe = pp["sd_safe"]
            sd_list = []
            sd_r = pp["sd_r"]
            for i in range(sd_n):
                a = i * 2.0 * math.pi / sd_n
                wx, wy, mvx, mvy = self.carry_velocity(k, a, bx, by)
                dvx, dvy = wx - bvx, wy - bvy
                dv = math.hypot(dvx, dvy)
                if dv > KICK or dv < 1e-6:
                    continue
                nx, ny = after_move(k, mvx, mvy)
                if kmove is None and (nx - bx) ** 2 + (ny - by) ** 2 > (KR - 0.05) ** 2:
                    continue
                b5x = bx + wx * G5
                b5y = by + wy * G5
                if abs(b5x) > XM - 1.0 or abs(b5y) > YM - 1.0:
                    continue
                b3x = bx + wx * G3
                b3y = by + wy * G3
                margin = 99.0
                for o in theirs:
                    # Lower bound from distance alone; exact reach only if it
                    # could matter (margins above 10 are all treated alike).
                    d5 = math.hypot(o.x - b5x, o.y - b5y) - sd_r - o.drift
                    d3 = math.hypot(o.x - b3x, o.y - b3y) - sd_r - o.drift
                    lb = min(d5 * 2.5 - 5, d3 * 2.5 - 3)
                    if lb >= 10.0 or lb >= margin:
                        continue
                    m1 = reach_ticks(o.x, o.y, o.vx, o.vy, b5x, b5y, sd_r) - 5
                    m2 = reach_ticks(o.x, o.y, o.vx, o.vy, b3x, b3y, sd_r) - 3
                    m = m1 if m1 < m2 else m2
                    if m < margin:
                        margin = m
                if margin < sd_safe:
                    continue
                v = (self.pos_value(b5x, b5y) + pp["sd_bonus"] * min(margin, 10.0) / 10.0
                     + pp["sd_fwd"] * (b5x - bx))
                act = (dvx / dv, dvy / dv, dv / KICK, None, None, (mvx, mvy))
                sd_list.append((v, b5x, b5y, wx * F5, wy * F5, act))
                if v > bestv:
                    bestv = v
                    best = act
                    best_feat = None
            # The strike each of the best few headings sets up at the next touch.
            sd_list.sort(key=lambda e: -e[0])
            for v, b5x, b5y, w5x, w5y, act in sd_list[:int(pp["sd_shot_k"])]:
                if b5x < pp["sd_shot_x"]:
                    continue
                if perf() - t0 > budget * 0.5:
                    break
                sv = pp["sd_shot_w"] * self.shot_value_from(theirs, b5x, b5y, 5, w5x, w5y)
                if sv > bestv:
                    bestv = sv
                    best = act
                    best_feat = None

        # Anytime order: a compact first pass, refine the best three right away
        # (the chosen kick usually comes from refinement), then the rest of the
        # candidates and a second refinement.
        dgoal = math.hypot(XL - bx, by)
        rng = pp["shot_range"]
        if pp["shot_kd"] > 0.0:
            rng = min(rng, pp["shot_r0"] + pp["shot_kd"] * self.gk_depth)
        shots_on = dgoal < rng
        da = pp["refine_da"]
        dc = pp["refine_dc"]
        refined = set()

        def shots(n):
            for si in range(n):
                if over():
                    return
                gy = -6.0 + 12.0 * si / (n - 1) if n > 1 else 0.0
                dx, dy = XL - bx, gy - by
                d = math.hypot(dx, dy)
                try_t(dx / d, dy / d, BALL_CAP, False)

        def refine(k_best):
            scored.sort(key=lambda e: -e[0])
            n_ref = 0
            for v0, kind, a, sp in scored:
                if n_ref >= k_best or over():
                    return
                key = (kind, round(a, 3), round(sp, 2))
                if key in refined:
                    continue
                refined.add(key)
                n_ref += 1
                if kind == "c":
                    for aa in (a - dc, a + dc):
                        if over():
                            return
                        try_c(aa, False)
                else:
                    for aa, ss in ((a - da, sp), (a + da, sp), (a, sp * 0.7),
                                   (a, min(sp * 1.35, BALL_CAP))):
                        if over():
                            return
                        try_t(math.cos(aa), math.sin(aa), ss, False)

        sp_hi = pp["c_drib_speeds"][-1]
        for c, s2 in fan(int(pp["c_drib_n"])):
            if over():
                break
            try_t(c, s2, sp_hi, True)
        for m in mine:
            if m.id == k.id or over():
                continue
            dx, dy = m.x - bx, m.y - by
            d = math.hypot(dx, dy)
            if d >= 3:
                try_t(dx / d, dy / d, pp["c_vends"][0] + d / ROLL, True)
        if shots_on:
            shots(int(pp["shot_n1"]))
        refine(2)
        for c, s2 in fan(int(pp["c_clear_n"])):
            if over():
                break
            try_t(c, s2, BALL_CAP, True)
        for c, s2 in fan(int(pp["c_drib_n"])):
            for sp in pp["c_drib_speeds"][:-1]:
                if over():
                    break
                try_t(c, s2, sp, True)
        refine(2)
        nc = int(pp["c_carry_n"])
        for c, s2 in fan(nc):
            if over():
                break
            try_c(math.atan2(s2, c), True)
        for m in mine:
            if m.id == k.id or over():
                continue
            for lead in pp["c_leads"]:
                if lead == 0.0:
                    continue
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
        if shots_on and int(pp["shot_n"]) > int(pp["shot_n1"]) and not over():
            shots(int(pp["shot_n"]))
        refine(int(pp["refine_k"]))
        if pp["la_k"] > 0 and not done:
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
                if v2 > bestv:
                    bestv = v2
                    best = act
                    best_feat = None
        if log_on and pool:
            if self.rng.random() < pp["log_eps"]:
                pool.sort(key=lambda e: -e[0])
                v0, best, best_feat = pool[self.rng.randrange(min(6, len(pool)))]
        self.chosen_feat = best_feat
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
