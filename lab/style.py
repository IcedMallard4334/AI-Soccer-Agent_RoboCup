"""Style statistics of a matchup, the numbers plan.md 10.1/10.2 accepts proxies on.

    py -3 lab/style.py lab/teams/v54.py lab/teams/selfkeep.py --seeds 7300..7314

Team A (first) is "us" (searched at max_evals 32, budget 1.0 if it has .p);
both ends of every seed. Per side: possession share, kicks, kicks under 0.3
power, shots (a kick of power >= 0.6 from within 35 of goal heading at it),
mean consecutive own kicks per possession, mean regain time (ticks from the
other side's possession starting to our next kick), share of their
possessions over 100 ticks, goals, and the share of 0-0 matches.
"""

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import bootstrap  # noqa: E402

bootstrap.ensure_engine()
from soccer import SoccerEnv  # noqa: E402
from soccer.helpers import load_controller  # noqa: E402
from soccer.runner import _native  # noqa: E402


OVERRIDE = {}   # extra parameters for team A (set by lab/paired.py)


def load(spec, over=None):
    if spec in _native.baseline_names():
        return None
    t = load_controller(os.path.join(ROOT, spec))
    if hasattr(t, "p"):
        t.p.update(budget=1.0, max_evals=32)
        if over:
            t.p.update(over)
    return t


def play(args):
    a_spec, b_spec, seed, swap = args
    a = load(a_spec, OVERRIDE)
    b = load(b_spec)
    env = SoccerEnv(per_decision_timeout_ms=1000)
    if b is None:
        env.use_baseline(1, b_spec)
    a.reset(seed)
    f = a.initial_formation(env.field)
    if f:
        env.set_formation(0, f)
    if b is not None:
        b.reset(seed)
        f = b.initial_formation(env.field)
        if f:
            env.set_formation(1, f)
    obs = env.reset(seed=seed, kickoff_team=1 if swap else 0)
    poss = [0, 0]
    kicks = [0, 0]
    soft = [0, 0]
    shots = [0, 0]
    runs = [[], []]      # consecutive kicks per possession, per side
    long_poss = [0, 0]   # possessions over 100 ticks, per side
    n_poss = [0, 0]
    regain = [[], []]    # ticks for side s to kick after the other side took over
    cur_team = None
    cur_start = 0
    cur_run = 0
    last_kick_team = None
    passes = [0, 0]      # struck kicks (>= 0.5) next touched by a different team-mate
    pass_dist = [0.0, 0.0]
    struck = [0, 0]      # struck kicks that are not shots (attempted passes)
    last = None          # (team, player, power, x, y, shot) of the previous kick
    while not env.finished:
        o = obs["team_a"]
        t = o.ball.controlling_team
        poss[t] += 1
        if t != cur_team:
            if cur_team is not None:
                n_poss[cur_team] += 1
                if o.tick - cur_start > 100:
                    long_poss[cur_team] += 1
            cur_team = t
            cur_start = o.tick
        for e in o.events:
            if e["kind"] == "goal":
                last = None
            if e["kind"] != "kick":
                continue
            s = e["team"]
            kicks[s] += 1
            if e["power"] < 0.3:
                soft[s] += 1
            bx, by = o.ball.position
            sign = 1.0 if s == 0 else -1.0
            dx = e["direction"]["x"] * sign
            dgx = 50.0 - bx * sign
            is_shot = e["power"] >= 0.6 and dgx < 35.0 and dx > 0.0 and abs(e["direction"]["y"] / dx) < 0.7
            if is_shot:
                shots[s] += 1
            if last is not None and last[0] == s and last[1] != e["player"] and last[2] >= 0.5 and not last[5]:
                passes[s] += 1
                pass_dist[s] += ((bx - last[3]) ** 2 + (by - last[4]) ** 2) ** 0.5
            if e["power"] >= 0.5 and not is_shot:
                struck[s] += 1
            last = (s, e["player"], e["power"], bx, by, is_shot)
            if s == last_kick_team:
                cur_run += 1
            else:
                if last_kick_team is not None:
                    runs[last_kick_team].append(cur_run)
                    regain[s].append(o.tick - cur_start if cur_team == s else 0)
                last_kick_team = s
                cur_run = 1
        acts = {"team_a": a.act(o)}
        if b is not None:
            acts["team_b"] = b.act(obs["team_b"])
        obs, _ = env.step(acts)
    sc = env.score
    return poss, kicks, soft, shots, runs, long_poss, n_poss, regain, sc, (passes, pass_dist, struck)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--seeds", default="7300..7314")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    s0, s1 = a.seeds.split("..")
    jobs = [(a.a, a.b, s, w) for s in range(int(s0), int(s1) + 1) for w in (False, True)]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        res = list(pool.map(play, jobs))
    P = [0, 0]
    K = [0, 0]
    S = [0, 0]
    SH = [0, 0]
    R = [[], []]
    LP = [0, 0]
    NP = [0, 0]
    RG = [[], []]
    G = [0, 0]
    wdl = [0, 0, 0]
    zz = 0
    PS = [0, 0]
    PD = [0.0, 0.0]
    ST = [0, 0]
    for poss, kicks, soft, shots, runs, lp, npo, rg, sc, (ps, pd, stc) in res:
        for s in (0, 1):
            PS[s] += ps[s]
            PD[s] += pd[s]
            ST[s] += stc[s]
        for s in (0, 1):
            P[s] += poss[s]
            K[s] += kicks[s]
            S[s] += soft[s]
            SH[s] += shots[s]
            R[s] += runs[s]
            LP[s] += lp[s]
            NP[s] += npo[s]
            RG[s] += [x for x in rg[s] if x > 0]
            G[s] += sc[s]
        wdl[0 if sc[0] > sc[1] else 1 if sc[0] == sc[1] else 2] += 1
        zz += sc[0] == 0 and sc[1] == 0
    n = len(res)
    print("%s vs %s, %d matches: W-D-L %d-%d-%d, 0-0 %.0f%%" % (
        os.path.basename(a.a), os.path.basename(a.b), n, wdl[0], wdl[1], wdl[2], 100.0 * zz / n))
    for s, nm in ((0, "us  "), (1, "them")):
        tot = P[0] + P[1]
        print("%s poss %4.1f%%  kicks/m %5.1f  soft %4.0f%%  shots/m %4.1f  goals/m %4.2f  "
              "kicks/poss %4.1f  long poss %4.0f%%  regain %5.1f ticks" % (
                  nm, 100.0 * P[s] / tot, K[s] / n, 100.0 * S[s] / max(1, K[s]), SH[s] / n, G[s] / n,
                  sum(R[s]) / max(1, len(R[s])), 100.0 * LP[s] / max(1, NP[s]),
                  sum(RG[s]) / max(1, len(RG[s]))))
        print("     passes/m %5.1f  pass dist/m %6.1f  completion %4.0f%%" % (
            PS[s] / n, PD[s] / n, 100.0 * PS[s] / max(1, ST[s])))


if __name__ == "__main__":
    main()
