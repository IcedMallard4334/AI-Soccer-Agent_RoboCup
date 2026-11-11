"""Benchmark a team against many opponents over many seeds, in parallel.

    py -3 lab/bench.py my-team/team.py --vs elite tactical balanced --seeds 1000..1019
    py -3 lab/bench.py lab/teams/v2.py --vs lab/teams/v1.py

Each seed is played from both ends (kickoff alternating), as the ladder does.
"""

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bootstrap  # noqa: E402

bootstrap.ensure_engine()
from soccer.runner import _build_fixtures, _run_fixture  # noqa: E402

DEFAULT_OPPS = ["elite", "tactical", "balanced", "possession", "man_marking",
                "structured_attack", "ball_chaser"]


def parse_seeds(text):
    if ".." in text:
        a, b = text.split("..")
        return list(range(int(a), int(b) + 1))
    return [int(s) for s in text.split(",")]


def job(args):
    team, opp, fixture, timeout = args
    r = _run_fixture(team, opp, fixture, None, None, None, timeout, None)
    st = (r.get("stats") or [{}, {}])[0]
    dt = st.get("decision_time_ms", {}) or {}
    return (opp, fixture["seed"], fixture["swapped"], r["score"][0], r["score"][1],
            r.get("platform_error"), st.get("policy_errors", 0),
            st.get("policy_timeouts", 0), st.get("fouls", 0),
            dt.get("total_ms", 0.0), dt.get("count", 0), dt.get("max_ms", 0.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("team")
    ap.add_argument("--vs", nargs="*", default=DEFAULT_OPPS)
    ap.add_argument("--seeds", default="1000..1019")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--timeout", type=float, default=None,
                    help="per-decision deadline in ms (default: config, 20)")
    a = ap.parse_args()
    seeds = parse_seeds(a.seeds)
    jobs = [(a.team, opp, fx, a.timeout) for opp in a.vs for fx in _build_fixtures(seeds, True)]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        rows = list(pool.map(job, jobs, chunksize=2))
    tot = {"W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0}
    ms_tot = ms_cnt = 0
    ms_max = 0.0
    print(f"{'opponent':40s}   W   D   L    GF   GA   errs fouls")
    for opp in a.vs:
        rs = [r for r in rows if r[0] == opp]
        w = sum(1 for r in rs if r[3] > r[4])
        d = sum(1 for r in rs if r[3] == r[4])
        l = sum(1 for r in rs if r[3] < r[4])
        gf = sum(r[3] for r in rs)
        ga = sum(r[4] for r in rs)
        errs = sum((r[6] or 0) + (r[7] or 0) for r in rs) + sum(1 for r in rs if r[5])
        fouls = sum(r[8] or 0 for r in rs)
        for k, v in zip("WDL", (w, d, l)):
            tot[k] += v
        tot["GF"] += gf
        tot["GA"] += ga
        ms_tot += sum(r[9] for r in rs)
        ms_cnt += sum(r[10] for r in rs)
        ms_max = max([ms_max] + [r[11] for r in rs])
        print(f"{os.path.basename(opp):40s} {w:3d} {d:3d} {l:3d} {gf:5d} {ga:4d} {errs:6d} {fouls:5d}")
        if a.verbose:
            for r in rs:
                if r[3] <= r[4] or r[5]:
                    print("    seed", r[1], "away" if r[2] else "home", r[3], "-", r[4], r[5] or "")
    n = tot["W"] + tot["D"] + tot["L"]
    print(f"{'TOTAL':40s} {tot['W']:3d} {tot['D']:3d} {tot['L']:3d} {tot['GF']:5d} {tot['GA']:4d}"
          f"   win%={100.0 * tot['W'] / max(n, 1):.1f}")
    print(f"decision mean {ms_tot / max(ms_cnt, 1):.3f} ms, max {ms_max:.2f} ms;"
          f" wall {time.time() - t0:.1f}s for {n} matches")
    for r in rows:
        if r[5]:
            print("PLATFORM ERROR", r[0], r[1], r[5])
            break


if __name__ == "__main__":
    main()
