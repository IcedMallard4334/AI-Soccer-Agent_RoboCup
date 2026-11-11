"""cProfile of non-kick ticks only (choose_kick excluded), one match vs elite;
with KICK=1 in the environment, of choose_kick only.
    py -3 lab/offprof.py lab/teams/v51_a1.py 1002"""
import cProfile, os, pstats, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bootstrap; bootstrap.ensure_engine()
from soccer import SoccerEnv
from soccer.helpers import load_controller
ctl = load_controller(os.path.join(ROOT, sys.argv[1])); seed = int(sys.argv[2])
ctl.p.update(budget=1.0, max_evals=32)
import json; ctl.p.update(json.loads(os.environ.get("P", "{}")))
env = SoccerEnv(per_decision_timeout_ms=1000); env.use_baseline(1, "elite")
env.set_formation(0, ctl.initial_formation(env.field)); ctl.reset(seed)
obs = env.reset(seed=seed, kickoff_team=0)
orig = ctl.choose_kick; prof = cProfile.Profile()
KICK = os.environ.get("KICK") == "1"
def ck(*a):
    if KICK:
        prof.enable(); r = orig(*a); prof.disable(); return r
    prof.disable(); r = orig(*a); prof.enable(); return r
ctl.choose_kick = ck
while not env.finished:
    if KICK:
        act = ctl.act(obs["team_a"])
    else:
        prof.enable(); act = ctl.act(obs["team_a"]); prof.disable()
    obs, _ = env.step({"team_a": act})
pstats.Stats(prof).sort_stats("tottime").print_stats(18)
