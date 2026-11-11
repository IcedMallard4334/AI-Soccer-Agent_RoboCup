"""Collect state-value training rows from matches played by a team module.

Every 4 ticks, from the point of view of the team in possession: ball (x, y),
how many defending outfield players are goal-side of the ball, how many
attacking outfield players are ahead of it, the nearest defender's distance,
and the label: +1 if the possessing team scores the next goal within H
ticks, -1 if it concedes it, else 0.

    py -3 lab/vlog.py v47 --seeds 7100..7129 --out lab/vlog.json
"""

import argparse
import json
import math
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

H = 600
POOL = ["lab/teams/v38cap.py", "lab/teams/v41cap.py", "lab/teams/midtable.py",
        "lab/teams/v3.py", "lab/teams/v1.py", "lab/teams/bus.py", "elite", "self"]


def ctl(spec, mod):
    if spec == "self":
        t = __import__(mod).MyTeam()
        t.p.update(budget=1.0, max_evals=32)
        return t
    if spec in _native.baseline_names():
        return None
    return load_controller(os.path.join(ROOT, spec))


def run(args):
    mod, opp, seed, kickoff = args
    a = __import__(mod).MyTeam()
    a.p.update(budget=1.0, max_evals=32)
    b = ctl(opp, mod)
    env = SoccerEnv(per_decision_timeout_ms=1000)
    if b is None:
        env.use_baseline(1, opp)
    a.reset(seed)
    if b is not None:
        f = b.initial_formation(env.field)
        if f:
            env.set_formation(1, f)
        b.reset(seed)
    obs = env.reset(seed=seed, kickoff_team=kickoff)
    snaps = []
    goals = []
    while not env.finished:
        oa = obs["team_a"]
        for ev in oa.events:
            if ev["kind"] == "goal":
                goals.append((oa.tick, ev["team"]))
        if oa.tick % 4 == 0:
            team = oa.ball.controlling_team
            bx, by = oa.ball.position
            att = oa.my_players if team == 0 else oa.opponents
            dfn = oa.opponents if team == 0 else oa.my_players
            s = 1.0 if team == 0 else -1.0
            x, y = bx * s, by * s
            ndef = sum(1 for q in dfn[1:] if q.position[0] * s > x)
            natt = sum(1 for q in att[1:] if q.position[0] * s > x)
            near = min(math.hypot(q.position[0] - bx, q.position[1] - by) for q in dfn[1:])
            snaps.append((oa.tick, team, x, y, ndef, natt, near))
        acts = {"team_a": a.act(obs["team_a"])}
        if b is not None:
            acts["team_b"] = b.act(obs["team_b"])
        obs, _ = env.step(acts)
    rows = []
    gi = 0
    for tick, team, x, y, ndef, natt, near in snaps:
        while gi < len(goals) and goals[gi][0] <= tick:
            gi += 1
        lab = 0
        if gi < len(goals) and goals[gi][0] - tick <= H:
            lab = 1 if goals[gi][1] == team else -1
        rows.append((round(x, 2), round(abs(y), 2), ndef, natt, round(near, 2), lab))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mod")
    ap.add_argument("--seeds", default="7100..7129")
    ap.add_argument("--out", default=os.path.join(HERE, "vlog.json"))
    a = ap.parse_args()
    s0, s1 = a.seeds.split("..")
    jobs = [(a.mod, opp, s, k) for opp in POOL for s in range(int(s0), int(s1) + 1) for k in (0, 1)]
    rows = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        for r in pool.map(run, jobs, chunksize=2):
            rows.extend(r)
    json.dump(rows, open(a.out, "w"))
    print("rows", len(rows), "matches", len(jobs))


if __name__ == "__main__":
    main()
