"""Collect (features, outcome) rows for every kick a logging team chooses.

    py -3 lab/collect.py v45 --seeds 7000..7029 --out lab/kicklog.json [--pool opp ...]
Rows: ("k", margin, mt, speed, rx, free, kept) or ("g", margin, gt, speed, bx, by, goal).
"""

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(HERE, "teams"))
import bootstrap  # noqa: E402

bootstrap.ensure_engine()
from soccer import SoccerEnv  # noqa: E402
from soccer.helpers import load_controller  # noqa: E402
from soccer.runner import _native  # noqa: E402

POOL = ["lab/teams/v38cap.py", "lab/teams/v41cap.py", "lab/teams/midtable.py",
        "lab/teams/v3.py", "lab/teams/v1.py", "lab/teams/bus.py", "elite"]


def run(args):
    mod, opp, seed, kickoff, eps = args
    m = __import__(mod)
    t = m.MyTeam()
    t.p.update(budget=1.0, max_evals=32, log_on=1, log_eps=eps)
    t.reset(seed)
    t.rng.seed(seed * 2 + kickoff)
    env = SoccerEnv(per_decision_timeout_ms=1000)
    o = None
    if opp in _native.baseline_names():
        env.use_baseline(1, opp)
    else:
        o = load_controller(os.path.join(ROOT, opp))
        f = o.initial_formation(env.field)
        if f:
            env.set_formation(1, f)
        o.reset(seed)
    obs = env.reset(seed=seed, kickoff_team=kickoff)
    while not env.finished:
        acts = {"team_a": t.decide(obs["team_a"])}
        if o is not None:
            acts["team_b"] = o.act(obs["team_b"])
        obs, _ = env.step(acts)
    return [list(r) for r in t.log_rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mod")
    ap.add_argument("--seeds", default="7000..7029")
    ap.add_argument("--eps", type=float, default=0.15)
    ap.add_argument("--out", default=os.path.join(HERE, "kicklog.json"))
    ap.add_argument("--pool", nargs="*", default=POOL)
    a = ap.parse_args()
    s0, s1 = a.seeds.split("..")
    jobs = [(a.mod, opp, s, k, a.eps) for opp in a.pool for s in range(int(s0), int(s1) + 1) for k in (0, 1)]
    rows = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        for r in pool.map(run, jobs, chunksize=2):
            rows.extend(r)
    json.dump(rows, open(a.out, "w"))
    nk = sum(1 for r in rows if r[0] == "k")
    print("rows", len(rows), "keep", nk, "kept rate %.3f" % (sum(r[6] for r in rows if r[0] == "k") / max(nk, 1)),
          "shots", len(rows) - nk, "goal rate %.3f" % (sum(r[6] for r in rows if r[0] == "g") / max(len(rows) - nk, 1)))


if __name__ == "__main__":
    main()
