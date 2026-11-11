"""Paired comparison (plan.md 12.1): team B against team A on identical
fixtures (same opponent, seed and end), reporting the mean per-match
difference B - A with its standard error, for points, goal difference,
goals for, shots, possession and regain time.

    py -3 lab/paired.py lab/teams/v54.py lab/teams/v55.py --vs lab/teams/selfkeep.py --seeds 7700..7729

Overrides: A_P / B_P environment variables (JSON) are applied to A / B after
the usual budget 1.0, max_evals 32.
"""

import argparse
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style  # noqa: E402


def job(args):
    side, spec, opp, seed, swap = args
    over = json.loads(os.environ.get(side + "_P", "{}"))
    style.OVERRIDE = over
    poss, kicks, soft, shots, runs, lp, npo, rg, sc, (ps, pd, stc) = style.play((spec, opp, seed, swap))
    tot = poss[0] + poss[1]
    reg = [x for x in rg[0] if x > 0]
    return {
        "pts": 3 if sc[0] > sc[1] else 1 if sc[0] == sc[1] else 0,
        "gd": sc[0] - sc[1],
        "gf": sc[0],
        "ga": sc[1],
        "shots": shots[0],
        "poss": 100.0 * poss[0] / tot,
        "regain": sum(reg) / len(reg) if reg else 0.0,
        "their_long": 100.0 * lp[1] / max(1, npo[1]),
        "passes": ps[0],
        "pass_dist": pd[0],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--vs", nargs="+", required=True)
    ap.add_argument("--seeds", default="7700..7729")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    s0, s1 = a.seeds.split("..")
    fx = [(o, s, w) for o in a.vs for s in range(int(s0), int(s1) + 1) for w in (False, True)]
    jobs = [("A", a.a) + f for f in fx] + [("B", a.b) + f for f in fx]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        res = list(pool.map(job, jobs, chunksize=2))
    n = len(fx)
    ra, rb = res[:n], res[n:]
    keys = ["pts", "gd", "gf", "ga", "shots", "passes", "pass_dist", "poss", "their_long"]
    print("B = %s minus A = %s, %d paired matches" % (os.path.basename(a.b), os.path.basename(a.a), n))
    for opp in a.vs + ["ALL"]:
        idx = [i for i, f in enumerate(fx) if opp == "ALL" or f[0] == opp]
        line = []
        for k in keys:
            d = [rb[i][k] - ra[i][k] for i in idx]
            m = sum(d) / len(d)
            sd = math.sqrt(sum((x - m) ** 2 for x in d) / max(1, len(d) - 1))
            se = sd / math.sqrt(len(d))
            base = sum(ra[i][k] for i in idx) / len(idx)
            line.append("%s %.2f %+.2f+-%.2f" % (k, base, m, se))
        print("%-14s n=%3d  " % (os.path.basename(opp)[:14], len(idx)) + "  ".join(line))


if __name__ == "__main__":
    main()
