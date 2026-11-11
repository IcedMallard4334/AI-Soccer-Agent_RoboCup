"""What happens after kickoffs? Plays matches the way the ladder server does
(neither side's initial_formation is applied: engine default spots) and,
for every kickoff (tick 0 and after each goal), records who kicked off and
whether that side scores / concedes within H ticks, and holds the ball at
+50 / +100 ticks.

    py -3 lab/kickoffs.py lab/teams/v60.py --vs lab/teams/selfkeep.py elite --seeds 9100..9114
A_P (JSON, environment) overrides team A's parameters (after budget 1.0,
max_evals 32). Prints, for kickoffs taken by A and by the opponent: count,
goals for A within H, goals against within H, A's possession at +50/+100.
"""

import argparse
import json
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

H = 300


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
    a = load(a_spec, json.loads(os.environ.get("A_P", "{}")))
    b = load(b_spec)
    env = SoccerEnv(per_decision_timeout_ms=1000)
    if b is None:
        env.use_baseline(1, b_spec)
    a.reset(seed)
    if b is not None:
        b.reset(seed)
    obs = env.reset(seed=seed, kickoff_team=1 if swap else 0)
    kicks = [(0, 1 if swap else 0)]   # (tick, kicking team)
    goals = []                        # (tick, team)
    poss = {}
    while not env.finished:
        o = obs["team_a"]
        poss[o.tick] = o.ball.controlling_team
        for e in o.events:
            if e["kind"] == "goal":
                goals.append((o.tick, e["team"]))
                kicks.append((o.tick, 1 - e["team"]))
        acts = {"team_a": a.act(o)}
        if b is not None:
            acts["team_b"] = b.act(obs["team_b"])
        obs, _ = env.step(acts)
    out = []
    for t0, team in kicks:
        gf = any(t0 < t <= t0 + H and g == 0 for t, g in goals)
        ga = any(t0 < t <= t0 + H and g == 1 for t, g in goals)
        p50 = poss.get(t0 + 50)
        p100 = poss.get(t0 + 100)
        out.append((team, gf, ga, p50, p100))
    return out, env.score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("--vs", nargs="+", required=True)
    ap.add_argument("--seeds", default="9100..9114")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    s0, s1 = a.seeds.split("..")
    jobs = [(a.a, o, s, w) for o in a.vs for s in range(int(s0), int(s1) + 1) for w in (False, True)]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        res = list(pool.map(play, jobs))
    agg = {0: [0, 0, 0, 0, 0], 1: [0, 0, 0, 0, 0]}
    gf = ga = 0
    for out, sc in res:
        gf += sc[0]
        ga += sc[1]
        for team, f, g, p50, p100 in out:
            e = agg[team]
            e[0] += 1
            e[1] += f
            e[2] += g
            e[3] += p50 == 0
            e[4] += p100 == 0
    print("%d matches, goals %d-%d" % (len(res), gf, ga))
    for team, name in ((0, "our kickoffs  "), (1, "their kickoffs")):
        n, f, g, p50, p100 = agg[team]
        print("%s n=%4d  we score within %d: %5.1f%%  they score: %5.1f%%  ours at +50: %5.1f%%  +100: %5.1f%%" % (
            name, n, H, 100.0 * f / max(1, n), 100.0 * g / max(1, n), 100.0 * p50 / max(1, n), 100.0 * p100 / max(1, n)))


if __name__ == "__main__":
    main()
