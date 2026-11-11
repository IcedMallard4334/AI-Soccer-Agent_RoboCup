"""Where does per-tick time go? Buckets: kick ticks vs non-kick, attacking vs defending."""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "lab", "teams"))
import bootstrap; bootstrap.ensure_engine()
from soccer import SoccerEnv
from soccer.helpers import load_controller
team = sys.argv[1]; opp = sys.argv[2]; seed = int(sys.argv[3])
ctl = load_controller(os.path.join(ROOT, team))
env = SoccerEnv(per_decision_timeout_ms=1000)
o = None
if opp in ("elite","tactical","balanced"): env.use_baseline(1, opp)
else:
    o = load_controller(os.path.join(ROOT, opp)); env.set_formation(1, o.initial_formation(env.field)); o.reset(seed)
env.set_formation(0, ctl.initial_formation(env.field)); ctl.reset(seed)
obs = env.reset(seed=seed, kickoff_team=0)
buckets = {}
orig_ck = ctl.choose_kick; flag = {"k": False}
def ck(*a):
    flag["k"] = True; return orig_ck(*a)
ctl.choose_kick = ck
while not env.finished:
    oa = obs["team_a"]; flag["k"] = False
    t0 = time.perf_counter(); act = ctl.act(oa); dt = (time.perf_counter()-t0)*1000
    key = ("kick" if flag["k"] else "nokick") + "/" + ("att" if oa.ball.controlling_team == 0 else "def")
    b = buckets.setdefault(key, [0, 0.0, 0.0]); b[0] += 1; b[1] += dt; b[2] = max(b[2], dt)
    acts = {"team_a": act}
    if o is not None: acts["team_b"] = o.act(obs["team_b"])
    obs, _ = env.step(acts)
tot = sum(b[1] for b in buckets.values()); n = sum(b[0] for b in buckets.values())
print(team, "vs", opp, "score", env.score, "mean %.3f ms" % (tot/n))
for k, (c, s, mx) in sorted(buckets.items()):
    print("%-12s n=%5d  mean %.3f ms  max %.2f  share %.0f%%" % (k, c, s/c, mx, 100*s/tot))
