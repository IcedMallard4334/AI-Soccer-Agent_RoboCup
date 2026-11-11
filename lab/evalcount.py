"""How many evaluations does the kick search get under a wall-clock budget?
One match vs elite, single process; prints the distribution of evaluations
per kick decision and how often the search stops short of max_evals.
    py -3 lab/evalcount.py my-team/team.py 0.0027
"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bootstrap; bootstrap.ensure_engine()
from soccer import SoccerEnv
from soccer.helpers import load_controller
t = load_controller(os.path.join(ROOT, sys.argv[1]))
t.p["budget"] = float(sys.argv[2])
env = SoccerEnv(per_decision_timeout_ms=1000); env.use_baseline(1, "elite")
env.set_formation(0, t.initial_formation(env.field)); t.reset(1002)
obs = env.reset(seed=1002, kickoff_team=0)
counts = []
orig_ck, orig_ev = t.choose_kick, t.evaluate
cur = [0]
def ev(*a, **k):
    cur[0] += 1
    return orig_ev(*a, **k)
def ck(*a):
    cur[0] = 0
    r = orig_ck(*a)
    counts.append(cur[0])
    return r
t.evaluate = ev; t.choose_kick = ck
while not env.finished:
    obs, _ = env.step({"team_a": t.act(obs["team_a"])})
counts.sort(); n = len(counts)
cap = t.base_p["max_evals"]
print("budget %.4f s: %d kick decisions, evaluations min %d p25 %d median %d p75 %d max %d; below 28: %.0f%%" % (
    t.p["budget"], n, counts[0], counts[n // 4], counts[n // 2], counts[3 * n // 4], counts[-1],
    100.0 * sum(1 for c in counts if c < 28) / n))
