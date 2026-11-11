"""Why does plan re-use fire or not? One match of a v54-style team vs elite."""
import collections, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bootstrap; bootstrap.ensure_engine()
from soccer import SoccerEnv
from soccer.helpers import load_controller
t = load_controller(os.path.join(ROOT, sys.argv[1])); t.p.update(budget=1.0, max_evals=32)
if len(sys.argv) > 3:
    t.p["reuse_k"] = int(sys.argv[3])
env = SoccerEnv(per_decision_timeout_ms=1000); env.use_baseline(1, sys.argv[2] if len(sys.argv) > 2 else "elite")
env.set_formation(0, t.initial_formation(env.field)); t.reset(1002)
obs = env.reset(seed=1002, kickoff_team=0)
why = collections.Counter()
orig = t.reuse_plan
def rp(o, mine, bx, by, tick, ko):
    c = t.plan_cache
    r = orig(o, mine, bx, by, tick, ko)
    if r is not None: why["reused"] += 1
    elif c is None: why["no cache"] += 1
    else:
        t0, pts, k0, tg = c; j = tick - t0
        if j >= t.base_p["reuse_k"]: why["age"] += 1
        elif j <= len(pts) and (abs(pts[j-1][0]-bx) > 0.05 or abs(pts[j-1][1]-by) > 0.05): why["ball moved off prediction"] += 1
        elif any(e.get("kind") in ("kick","goal","turnover","foul") for e in o.events): why["event"] += 1
        else: why["kicker near / other"] += 1
    return r
t.reuse_plan = rp
nc = 0
while not env.finished:
    obs, _ = env.step({"team_a": t.act(obs["team_a"])})
print(dict(why), "score", env.score)
