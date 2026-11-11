"""Learn a possession value grid (expected threat) from played matches.

For every tick, from the point of view of the team in possession: where is
the ball, and does that team score the next goal within H ticks (+1), concede
it (-1), or neither (0)? Averaged per grid cell this is the value of having
the ball there, in goals.

    py -3 lab/xt.py --pairs "lab/teams/v14ref.py:lab/teams/v3.py" ... --seeds 1000..1019
Writes lab/xt_grid.json and prints the grid.
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

NX, NY = 20, 6          # x in 5-unit bins over [-50, 50], |y| in 5-unit bins
H = 600


def ctl(spec):
    return None if spec in _native.baseline_names() else load_controller(spec)


def run(args):
    a_spec, b_spec, seed, kickoff = args
    teams = [ctl(a_spec), ctl(b_spec)]
    env = SoccerEnv(per_decision_timeout_ms=1000)
    for i, (spec, c) in enumerate(zip((a_spec, b_spec), teams)):
        if c is None:
            env.use_baseline(i, spec)
        else:
            f = c.initial_formation(env.field)
            if f:
                env.set_formation(i, f)
            c.reset(seed)
    obs = env.reset(seed=seed, kickoff_team=kickoff)
    ticks = []      # (tick, poss_team, x, y) in absolute team-A frame
    goals = []      # (tick, team)
    while not env.finished:
        oa = obs["team_a"]
        for ev in oa.events:
            if ev["kind"] == "goal":
                goals.append((oa.tick, ev["team"]))
        bx, by = oa.ball.position
        ticks.append((oa.tick, oa.ball.controlling_team, bx, by))
        acts = {}
        if teams[0] is not None:
            acts["team_a"] = teams[0].act(obs["team_a"])
        if teams[1] is not None:
            acts["team_b"] = teams[1].act(obs["team_b"])
        obs, _ = env.step(acts)
    sums = [[0.0] * NY for _ in range(NX)]
    cnts = [[0] * NY for _ in range(NX)]
    gi = 0
    for tick, team, x, y in ticks:
        while gi < len(goals) and goals[gi][0] <= tick:
            gi += 1
        label = 0
        if gi < len(goals) and goals[gi][0] - tick <= H:
            label = 1 if goals[gi][1] == team else -1
        if team == 1:
            x, y = -x, -y
        ix = min(NX - 1, max(0, int((x + 50.0) / 5.0)))
        iy = min(NY - 1, int(abs(y) / 5.0))
        sums[ix][iy] += label
        cnts[ix][iy] += 1
    return sums, cnts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="+", required=True)
    ap.add_argument("--seeds", default="1000..1019")
    ap.add_argument("--out", default=os.path.join(HERE, "xt_grid.json"))
    a = ap.parse_args()
    s0, s1 = a.seeds.split("..")
    jobs = []
    for pair in a.pairs:
        x, y = pair.split(":")
        for s in range(int(s0), int(s1) + 1):
            for k in (0, 1):
                jobs.append((x, y, s, k))
    sums = [[0.0] * NY for _ in range(NX)]
    cnts = [[0] * NY for _ in range(NX)]
    with ProcessPoolExecutor(max_workers=8) as pool:
        for s, c in pool.map(run, jobs):
            for i in range(NX):
                for j in range(NY):
                    sums[i][j] += s[i][j]
                    cnts[i][j] += c[i][j]
    grid = [[(sums[i][j] / cnts[i][j]) if cnts[i][j] else None for j in range(NY)] for i in range(NX)]
    json.dump({"grid": grid, "counts": cnts, "H": H, "matches": len(jobs)}, open(a.out, "w"))
    print("matches", len(jobs))
    for j in range(NY):
        print("|y|%2d-%2d " % (j * 5, j * 5 + 5) + " ".join(
            ("%5.2f" % grid[i][j]) if grid[i][j] is not None else "  .  " for i in range(NX)))
    print("        " + " ".join("%5d" % (-50 + i * 5) for i in range(NX)))


if __name__ == "__main__":
    main()
