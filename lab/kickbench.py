"""Deterministic speed benchmark for the kick search.

Captures the inputs of every kick decision in a few matches (played by the
first module), then times choose_kick of each module on exactly those inputs,
best of several repeats, with an unlimited time budget. Also reports how many
decisions differ from the first module's. Calls whose result is a list
(choose_kick(..., plan=True) searching ahead) are not captured. With
--max-evals N, p["max_evals"] is set to N in every case (a capped search).

    py -3 lab/kickbench.py v25 v26
    py -3 lab/kickbench.py v32 v32fast --max-evals 24
"""

import copy
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "teams"))
sys.path.insert(0, os.path.dirname(HERE))
import bootstrap  # noqa: E402

bootstrap.ensure_engine()
from soccer import SoccerEnv  # noqa: E402
from soccer.helpers import load_controller  # noqa: E402


def capture(mod, seeds=(1001, 1002), opp="lab/teams/v18ref.py"):
    cases = []
    for seed in seeds:
        t = mod.MyTeam()
        t.p["budget"] = 1.0
        t.reset(seed)
        o = load_controller(os.path.join(os.path.dirname(HERE), opp))
        o.reset(seed)
        env = SoccerEnv(per_decision_timeout_ms=1000)
        env.set_formation(0, t.initial_formation(env.field))
        env.set_formation(1, o.initial_formation(env.field))
        obs = env.reset(seed=seed, kickoff_team=0)
        orig = t.choose_kick

        def grab(*a, orig=orig, t=t):
            case = (copy.deepcopy(a), dict(t.p), t.threat)
            res = orig(*a)
            if not isinstance(res, list):
                cases.append(case)
            return res

        t.choose_kick = grab
        while not env.finished:
            obs, _ = env.step({"team_a": t.decide(obs["team_a"]), "team_b": o.act(obs["team_b"])})
    return cases


def run(mod, cases, reps=3, max_evals=None):
    t = mod.MyTeam()
    t.reset(1)
    best = None
    outs = []
    for rep in range(reps):
        outs = []
        t0 = time.perf_counter()
        for args, p, threat in cases:
            t.p = dict(mod.P)
            t.p.update(p)
            t.p["budget"] = 1.0
            if max_evals is not None:
                t.p["max_evals"] = max_evals
            t.base_p = t.p
            t.threat = threat
            t.t0 = time.perf_counter()
            a = t.choose_kick(*copy.deepcopy(args))
            outs.append((a.kick_direction, round(a.kick_power, 6)))
        el = time.perf_counter() - t0
        best = el if best is None else min(best, el)
    return best, outs


def main():
    args = sys.argv[1:]
    max_evals = None
    if "--max-evals" in args:
        i = args.index("--max-evals")
        max_evals = int(args[i + 1])
        del args[i:i + 2]
    mods = [__import__(m) for m in args]
    cases = capture(mods[0])
    ref = None
    for m in mods:
        el, outs = run(m, cases, max_evals=max_evals)
        if ref is None:
            ref = outs
        diff = sum(1 for a, b in zip(ref, outs) if a != b)
        print("%-8s %4d kicks  %.2f ms per kick  (%d differ from %s)" % (
            m.__name__, len(cases), el * 1000 / len(cases), diff, mods[0].__name__))


if __name__ == "__main__":
    main()
