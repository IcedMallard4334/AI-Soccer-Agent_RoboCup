"""Which style does v62's detector see against each opponent? One match per
opponent and end; prints the share of ticks in each detected mode.
    py -3 lab/detmodes.py lab/teams/selfkeep.py elite ...
"""
import json, os, sys
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style  # noqa: E402


def one(args):
    opp, seed, swap = args
    style.OVERRIDE = {"det_on": 1}
    a = style.load(os.environ.get("DET_TEAM", "lab/teams/v62.py"), json.loads(os.environ.get("DET_P", "{\"det_on\": 1}")))
    b = style.load(opp)
    env = style.SoccerEnv(per_decision_timeout_ms=1000)
    if b is None:
        env.use_baseline(1, opp)
    a.reset(seed)
    if b is not None:
        b.reset(seed)
    obs = env.reset(seed=seed, kickoff_team=1 if swap else 0)
    while not env.finished:
        acts = {"team_a": a.act(obs["team_a"])}
        if b is not None:
            acts["team_b"] = b.act(obs["team_b"])
        obs, _ = env.step(acts)
    return opp, dict(a.mode_ticks)


if __name__ == "__main__":
    jobs = [(o, s, w) for o in sys.argv[1:] for s in (9500, 9501) for w in (False, True)]
    with ProcessPoolExecutor(max_workers=8) as pool:
        res = list(pool.map(one, jobs))
    for o in sys.argv[1:]:
        tot = {}
        for oo, mt in res:
            if oo == o:
                for k, v in mt.items():
                    tot[k] = tot.get(k, 0) + v
        n = sum(tot.values()) or 1
        print("%-16s " % os.path.basename(o) + "  ".join("%s %3.0f%%" % (k, 100.0 * v / n) for k, v in sorted(tot.items())))
