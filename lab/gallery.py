"""Shooting gallery for our keeper (plan.md 26), in the real engine.

Our team plays as usual except that its four outfield players are sent out
of the way (to the far corners of the opponents' half), so only our keeper
defends. The scripted attacker dribbles to a random point 14-20 units from
our goal (angle within +-60 degrees), then strikes at the post away from our
keeper at full power (about 22-27 u/s on arrival), like the goals the top
ladder teams score on us. Counts their strikes and goals.

    py -3 lab/gallery.py lab/teams/v61.py --seeds 10200..10219
A_P (JSON, environment) overrides our parameters (after budget 1.0,
max_evals 32). Prints shots, goals and the save rate.
"""

import argparse
import json
import math
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import bootstrap  # noqa: E402

bootstrap.ensure_engine()
from soccer import PlayerAction, SoccerEnv, TeamAction  # noqa: E402
from soccer.helpers import load_controller  # noqa: E402

DT = 0.05
F = 0.985
G5 = DT * (1 - F ** 5) / (1 - F)


def unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-9 else (1.0, 0.0)


class Shooter:
    """Scripted attacker, in its own frame (attacking +x, our goal at +50)."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.target = None
        self.shots = 0

    def new_target(self):
        d = self.rng.uniform(14.0, 20.0)
        a = math.radians(self.rng.uniform(-60.0, 60.0))
        self.target = (50.0 - d * math.cos(a), d * math.sin(a))

    def act(self, obs):
        a = TeamAction()
        bx, by = obs.ball.position
        bvx, bvy = obs.ball.velocity
        if self.target is None:
            self.new_target()
        mates = obs.my_players
        carrier = min(mates[1:], key=lambda p: math.hypot(p.position[0] - bx, p.position[1] - by))
        keeper_y = obs.opponents[0].position[1]
        for p in mates:
            x, y = p.position
            if p.id != carrier.id:
                a.set(p.id, PlayerAction())
                continue
            if obs.can_kick(p.id):
                tx, ty = self.target
                if math.hypot(tx - bx, ty - by) < 2.5:
                    gy = -6.3 if keeper_y > 0 else 6.3
                    ux, uy = unit(50.0 - bx, gy - by)
                    dvx, dvy = ux * 30.0 - bvx, uy * 30.0 - bvy
                    dv = math.hypot(dvx, dvy) or 1.0
                    a.set(p.id, PlayerAction(movement=(0.0, 0.0), kick_direction=(dvx / dv, dvy / dv),
                                             kick_power=min(1.0, dv / 22.0)))
                    self.shots += 1
                    self.new_target()
                    continue
                ux, uy = unit(tx - bx, ty - by)
                sp = min(9.0, math.hypot(tx - bx, ty - by) / G5 * 0.8 + 2.0)
                dvx, dvy = ux * sp - bvx, uy * sp - bvy
                dv = math.hypot(dvx, dvy) or 1.0
                a.set(p.id, PlayerAction(movement=(ux, uy), kick_direction=(dvx / dv, dvy / dv),
                                         kick_power=min(1.0, dv / 22.0)))
                continue
            # Chase the ball, arriving from behind it relative to the target.
            tx, ty = self.target
            ux, uy = unit(tx - bx, ty - by)
            px, py = bx + bvx * 0.2 - ux * 1.0, by + bvy * 0.2 - uy * 1.0
            dx, dy = px - x, py - y
            d = math.hypot(dx, dy)
            s = min(1.0, d / 1.5)
            mx, my = unit(dx, dy)
            a.set(p.id, PlayerAction(movement=(mx * s, my * s)))
        return a


def play(args):
    spec, seed, swap = args
    t = load_controller(os.path.join(ROOT, spec))
    t.p.update(budget=1.0, max_evals=32)
    t.p.update(json.loads(os.environ.get("A_P", "{}")))
    sh = Shooter(seed * 2 + (1 if swap else 0))
    env = SoccerEnv(per_decision_timeout_ms=1000)
    t.reset(seed)
    obs = env.reset(seed=seed, kickoff_team=1 if swap else 0)
    while not env.finished:
        o = obs["team_a"]
        act = t.act(o)
        for q in o.my_players[1:]:
            x, y = q.position
            gy = 28.0 if q.id % 2 else -28.0
            mx, my = unit(45.0 - x, gy - y)
            act.set(q.id, PlayerAction(movement=(mx, my)))
        obs, _ = env.step({"team_a": act, "team_b": sh.act(obs["team_b"])})
    return sh.shots, env.score[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("team")
    ap.add_argument("--seeds", default="10200..10219")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    s0, s1 = a.seeds.split("..")
    jobs = [(a.team, s, w) for s in range(int(s0), int(s1) + 1) for w in (False, True)]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        res = list(pool.map(play, jobs))
    shots = sum(r[0] for r in res)
    goals = sum(r[1] for r in res)
    p = goals / max(1, shots)
    se = math.sqrt(p * (1 - p) / max(1, shots))
    print("%d matches: %d strikes, %d goals, %.1f%% scored (±%.1f), %.1f strikes per match" % (
        len(res), shots, goals, 100.0 * p, 100.0 * se, shots / len(res)))


if __name__ == "__main__":
    main()
