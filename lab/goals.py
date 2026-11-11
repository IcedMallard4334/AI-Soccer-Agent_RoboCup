"""Where do goals come from? Plays matches and logs, for every goal, the last
kick before it (position, power, speed after the kick, ticks before the goal)
and the keeper's position at the time of that kick.

    py -3 lab/goals.py lab/teams/v4.py lab/teams/v3.py --seeds 1000..1009
"""

import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bootstrap  # noqa: E402

bootstrap.ensure_engine()
from soccer import SoccerEnv  # noqa: E402
from soccer.helpers import load_controller  # noqa: E402


def run(args):
    a_spec, b_spec, seed, kickoff = args
    a = load_controller(a_spec)
    b = load_controller(b_spec)
    env = SoccerEnv(per_decision_timeout_ms=1000)
    for team, c in ((0, a), (1, b)):
        f = c.initial_formation(env.field)
        if f:
            env.set_formation(team, f)
    a.reset(seed)
    b.reset(seed)
    obs = env.reset(seed=seed, kickoff_team=kickoff)
    last_kick = None
    out = []
    while not env.finished:
        oa = obs["team_a"]
        for ev in oa.events:
            if ev["kind"] == "kick":
                pl = ev["player"]
                body = (oa.my_players + oa.opponents)[pl]
                keeper = oa.opponents[0] if ev["team"] == 0 else oa.my_players[0]
                last_kick = dict(tick=ev["tick"], team=ev["team"], pos=body.position,
                                 power=ev["power"], bspeed=math.hypot(*oa.ball.velocity),
                                 keeper=keeper.position)
            elif ev["kind"] == "goal":
                out.append(dict(goal_team=ev["team"], own=ev.get("own_goal"), tick=ev["tick"],
                                kick=last_kick))
        obs, _ = env.step({"team_a": a.act(obs["team_a"]), "team_b": b.act(obs["team_b"])})
    return out


def main():
    a_spec, b_spec = sys.argv[1], sys.argv[2]
    s0, s1 = sys.argv[3].split("..") if len(sys.argv) > 3 else ("1000", "1009")
    jobs = [(a_spec, b_spec, s, k) for s in range(int(s0), int(s1) + 1) for k in (0, 1)]
    with ProcessPoolExecutor(max_workers=8) as pool:
        res = list(pool.map(run, jobs))
    for team in (0, 1):
        print("=== goals for team", team, os.path.basename((a_spec, b_spec)[team]))
        n = 0
        for goals in res:
            for g in goals:
                if g["goal_team"] != team:
                    continue
                n += 1
                k = g["kick"]
                if k is None:
                    print("  no kick")
                    continue
                # Express in the scoring team's attacking frame (team 0 attacks +x).
                sx = 1 if team == 0 else -1
                x, y = k["pos"]
                kx, ky = k["keeper"]
                print("  own=%s kicker_team=%d from (%5.1f,%5.1f) dist %4.1f power %.2f speed %4.1f"
                      " dt %3d  keeper (%5.1f,%5.1f)" % (
                          g["own"], k["team"], x * sx, y, math.hypot(50 - x * sx, y), k["power"],
                          k["bspeed"], g["tick"] - k["tick"], kx * sx, ky))
        print("  total", n)


if __name__ == "__main__":
    main()
