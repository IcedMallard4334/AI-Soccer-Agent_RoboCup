"""Mean decision time of one team playing its own matches (not fed someone
else's observations), production settings, with P (JSON env) overrides.
    P='{"wall_on":1,"wall_min_lead":2}' py -3 lab/selftime.py lab/teams/v66.py elite bus 1002 1003
"""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bootstrap; bootstrap.ensure_engine()
from soccer import SoccerEnv
from soccer.helpers import load_controller
from soccer.runner import _native
team = sys.argv[1]; args = sys.argv[2:]
opps = [a for a in args if not a.isdigit()]; seeds = [int(a) for a in args if a.isdigit()]
tot = n = 0
for opp in opps:
    for seed in seeds:
        t = load_controller(os.path.join(ROOT, team)); t.p.update(json.loads(os.environ.get("P", "{}")))
        env = SoccerEnv(per_decision_timeout_ms=1000)
        o = None
        if opp in _native.baseline_names():
            env.use_baseline(1, opp)
        else:
            o = load_controller(os.path.join(ROOT, opp)); o.reset(seed)
        t.reset(seed)
        obs = env.reset(seed=seed, kickoff_team=0)
        while not env.finished:
            t0 = time.perf_counter(); a = t.act(obs["team_a"]); tot += time.perf_counter() - t0; n += 1
            acts = {"team_a": a}
            if o is not None:
                acts["team_b"] = o.act(obs["team_b"])
            obs, _ = env.step(acts)
print("mean %.3f ms over %d decisions" % (tot * 1000 / n, n))
