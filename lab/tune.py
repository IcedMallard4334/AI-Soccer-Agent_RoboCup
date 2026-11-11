"""(1+lambda) evolution strategy over team parameters.

Every generation the incumbent and `lam` mutants play the same fixtures (fresh
seeds each generation) against an opponent pool; the best mutant replaces the
incumbent only if it scored more on those same fixtures. Step size follows the
1/5 success rule. Progress goes to lab/tune_<name>.log, the incumbent to
lab/tune_<name>.json.

    py -3 lab/tune.py --base v18 --name t1 --gens 30
"""

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "teams"))
import sweep  # noqa: E402  (bootstraps the engine)
from soccer.runner import _build_fixtures  # noqa: E402

# name: (step, lo, hi)
SPACE = {
    "keep_bias": (1.0, -2.0, 5.0),
    "sig_keep": (0.6, 0.8, 6.0),
    "goal_bias": (0.8, -3.0, 4.0),
    "sig_goal": (0.5, 0.6, 5.0),
    "xt_scale": (0.5, 1.0, 5.0),
    "goal_units": (0.25, 0.5, 2.5),
    "lose_pen": (0.08, 0.0, 0.6),
    "r_get": (0.12, 1.5, 2.2),
    "hyst": (1.0, 0.0, 6.0),
    "sup_open": (0.05, 0.0, 0.4),
    "sup_lane": (0.05, 0.0, 0.4),
    "cover_dist": (2.0, 3.0, 16.0),
    "mark_goal_side": (0.7, 0.5, 5.0),
    "carry_lead": (0.12, 1.5, 2.15),
    "antic_t": (3.0, 0.0, 20.0),
    "la_k": (2.0, 0.0, 8.0),
}

POOL = ["lab/teams/v16ref.py", "lab/teams/v14ref.py", "lab/teams/v3.py",
        "lab/teams/v9ref.py", "lab/teams/v7ref.py", "lab/teams/v1.py"]


def mutate(params, sigma, rng, n_keys=4):
    child = dict(params)
    for k in rng.sample(sorted(SPACE), n_keys):
        step, lo, hi = SPACE[k]
        v = child[k] + rng.gauss(0.0, step * sigma)
        child[k] = round(min(hi, max(lo, v)), 3)
    return child


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--gens", type=int, default=30)
    ap.add_argument("--lam", type=int, default=4)
    ap.add_argument("--seeds", type=int, default=6, help="seeds per generation")
    ap.add_argument("--start", default=None, help="JSON of starting params")
    a = ap.parse_args()
    rng = random.Random(12345)
    base_mod = __import__(a.base)
    inc = {k: base_mod.P[k] for k in SPACE}
    if a.start:
        inc.update(json.loads(open(a.start).read()) if os.path.exists(a.start) else json.loads(a.start))
    sigma = 1.0
    log = open(os.path.join(HERE, "tune_%s.log" % a.name), "a")
    seed0 = 3000
    with ProcessPoolExecutor(max_workers=8) as pool:
        for gen in range(a.gens):
            seeds = list(range(seed0 + gen * a.seeds, seed0 + (gen + 1) * a.seeds))
            cands = [inc]
            while len(cands) < a.lam + 1:
                c = mutate(inc, sigma, rng)
                if all(c != o for o in cands):
                    cands.append(c)
            variants = sweep.make_variants(a.base, [dict(c, budget=1.0) for c in cands])
            jobs = [(path, opp, fx, 1000.0) for path, _ in variants for opp in POOL
                    for fx in _build_fixtures(seeds, True)]
            t0 = time.time()
            rows = list(pool.map(sweep.job, jobs, chunksize=1))
            scores = []
            for path, _ in variants:
                rs = [r for r in rows if r[0] == path]
                pts = sum(3 if r[2] > r[3] else 1 if r[2] == r[3] else 0 for r in rs)
                gd = sum(r[2] - r[3] for r in rs)
                scores.append(pts + 0.1 * gd)
            best_i = max(range(1, len(cands)), key=lambda i: scores[i])
            improved = scores[best_i] > scores[0]
            if improved:
                inc = cands[best_i]
                sigma = min(2.0, sigma * 1.3)
            else:
                sigma = max(0.3, sigma * 0.85)
            msg = "gen %d  inc %.1f  best mutant %.1f  %s  sigma %.2f  (%.0fs)\n" % (
                gen, scores[0], scores[best_i], "ACCEPT" if improved else "keep", sigma, time.time() - t0)
            log.write(msg)
            log.write("   incumbent " + json.dumps(inc) + "\n")
            log.flush()
            json.dump(inc, open(os.path.join(HERE, "tune_%s.json" % a.name), "w"), indent=1)
            print(msg, end="", flush=True)


if __name__ == "__main__":
    main()
