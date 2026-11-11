"""Single-process timing of a team: distribution of decision times.

    py -3 lab/timing.py lab/teams/v1.py --vs elite --seed 1001 [--profile]
"""

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bootstrap  # noqa: E402

bootstrap.ensure_engine()
from soccer import SoccerEnv  # noqa: E402
from soccer.helpers import load_controller  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("team")
    ap.add_argument("--vs", default="elite")
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--profile", action="store_true")
    a = ap.parse_args()
    ctl = load_controller(a.team)
    env = SoccerEnv()
    env.use_baseline(1, a.vs)
    f = ctl.initial_formation(env.field)
    if f:
        env.set_formation(0, f)
    ctl.reset(a.seed)
    obs = env.reset(seed=a.seed, kickoff_team=0)
    times = []
    prof = None
    if a.profile:
        import cProfile
        prof = cProfile.Profile()
    while not env.finished:
        o = obs["team_a"]
        t0 = time.perf_counter()
        if prof:
            prof.enable()
        act = ctl.act(o)
        if prof:
            prof.disable()
        times.append((time.perf_counter() - t0) * 1000)
        obs, _ = env.step({"team_a": act})
    times.sort()
    n = len(times)
    print("score", env.score, "ticks", n)
    print("mean %.3f  p50 %.3f  p90 %.3f  p99 %.3f  max %.3f ms" % (
        sum(times) / n, times[n // 2], times[int(n * .9)], times[int(n * .99)], times[-1]))
    print("over 10ms:", sum(1 for t in times if t > 10), " over 5ms:", sum(1 for t in times if t > 5))
    if prof:
        import pstats
        pstats.Stats(prof).sort_stats("cumulative").print_stats(15)


if __name__ == "__main__":
    main()
