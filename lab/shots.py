"""Shot accounting: for each team, every kick whose free path would enter the
opponent goal, and what actually happened to it.

    py -3 lab/shots.py lab/teams/v14ref.py lab/teams/v9ref.py 1000..1009
"""

import math
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(HERE, "teams"))
import bootstrap  # noqa: E402

bootstrap.ensure_engine()
from soccer import SoccerEnv  # noqa: E402
from soccer.helpers import load_controller  # noqa: E402
from v14 import ball_path  # noqa: E402


def run(args):
    a_spec, b_spec, seed, kickoff = args
    teams = [load_controller(a_spec), load_controller(b_spec)]
    env = SoccerEnv(per_decision_timeout_ms=1000)
    for i, c in enumerate(teams):
        f = c.initial_formation(env.field)
        if f:
            env.set_formation(i, f)
        c.reset(seed)
    obs = env.reset(seed=seed, kickoff_team=kickoff)
    open_shot = None   # (team, dist, speed, tick)
    rows = []
    while not env.finished:
        oa = obs["team_a"]
        for ev in oa.events:
            k = ev["kind"]
            if k == "goal":
                if open_shot is not None:
                    rows.append(open_shot + ("goal" if ev["team"] == open_shot[0] else "own",))
                    open_shot = None
            elif k == "kick":
                if open_shot is not None:
                    who = "keeper" if ev["player"] in (0, 5) else "field"
                    side = "same" if ev["team"] == open_shot[0] else "opp"
                    rows.append(open_shot + ("touched_%s_%s" % (side, who),))
                    open_shot = None
                team = ev["team"]
                bx, by = oa.ball.position
                vx, vy = oa.ball.velocity
                # Judge the shot in the kicking team's attacking frame.
                if team == 1:
                    bx, by, vx, vy = -bx, -by, -vx, -vy
                pts, gt, gs = ball_path(bx, by, vx, vy, 90)
                if gs == 1:
                    open_shot = (team, round(math.hypot(50 - bx, by)), round(math.hypot(vx, vy)), oa.tick)
        if open_shot is not None and oa.tick - open_shot[3] > 120:
            rows.append(open_shot + ("expired",))
            open_shot = None
        # Ball stopped by a body (no kick event): direction reversed or slowed hard.
        obs, _ = env.step({"team_a": teams[0].act(obs["team_a"]), "team_b": teams[1].act(obs["team_b"])})
        if open_shot is not None:
            ob = obs["team_a"]
            vx, vy = ob.ball.velocity
            if open_shot[0] == 1:
                vx = -vx
            if vx <= 0 and not any(e["kind"] == "goal" for e in ob.events):
                rows.append(open_shot + ("blocked",))
                open_shot = None
    return rows


def main():
    a, b = sys.argv[1], sys.argv[2]
    s0, s1 = sys.argv[3].split("..")
    jobs = [(a, b, s, k) for s in range(int(s0), int(s1) + 1) for k in (0, 1)]
    with ProcessPoolExecutor(max_workers=8) as pool:
        res = [r for rows in pool.map(run, jobs) for r in rows]
    for team in (0, 1):
        rs = [r for r in res if r[0] == team]
        print("== shots by", os.path.basename((a, b)[team]), len(rs))
        print("   outcomes:", dict(Counter(r[4] for r in rs)))
        for lo, hi in ((0, 12), (12, 18), (18, 24), (24, 32), (32, 200)):
            sub = [r for r in rs if lo <= r[1] < hi]
            g = sum(1 for r in sub if r[4] == "goal")
            if sub:
                print("   dist %2d-%3d: %3d shots, %2d goals, mean speed %.1f" % (
                    lo, hi, len(sub), g, sum(r[2] for r in sub) / len(sub)))


if __name__ == "__main__":
    main()
