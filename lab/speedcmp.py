"""Interleaved timing of two teams on the same observations (team A plays,
B is fed A's observations), so machine load hits both alike.
    py -3 lab/speedcmp.py lab/teams/v51.py lab/teams/v53.py [seed] [opponent]
Prints mean / p99 / max ms of each, split into kick and off-ball ticks, and
how many ticks B's actions differ from A's."""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bootstrap; bootstrap.ensure_engine()
from soccer import SoccerEnv
from soccer.helpers import load_controller

a = load_controller(os.path.join(ROOT, sys.argv[1])); b = load_controller(os.path.join(ROOT, sys.argv[2]))
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1002
opp = sys.argv[4] if len(sys.argv) > 4 else "elite"
import json
b.p.update(json.loads(os.environ.get("B_P", "{}")))
if os.environ.get("PROD") != "1":   # PROD=1: each team at its shipped settings
    for t in (a, b):
        t.p.update(budget=1.0, max_evals=32)
b.p.update(json.loads(os.environ.get("B_P", "{}")))
env = SoccerEnv(per_decision_timeout_ms=1000); env.use_baseline(1, opp)
env.set_formation(0, a.initial_formation(env.field)); a.reset(seed); b.reset(seed)
obs = env.reset(seed=seed, kickoff_team=0)
T = {"A": {"k": [], "o": []}, "B": {"k": [], "o": []}}
diff = 0
pc = time.perf_counter
while not env.finished:
    o = obs["team_a"]
    kick = any(o.can_kick(q.id) for q in o.my_players)
    key = "k" if kick else "o"
    order = (("A", a), ("B", b)) if o.tick % 2 == 0 else (("B", b), ("A", a))
    res = {}
    for name, t in order:
        t0 = pc(); res[name] = t.act(o); T[name][key].append((pc() - t0) * 1000)
    for pid in range(5):
        x = res["A"].players.get(pid); y = res["B"].players.get(pid)
        if (x and (x.movement, x.kick_direction, x.kick_power)) != (y and (y.movement, y.kick_direction, y.kick_power)):
            diff += 1
    obs, _ = env.step({"team_a": res["A"]})


def st(v):
    v = sorted(v)
    n = len(v)
    return "n=%5d mean %.3f p99 %.2f max %.2f" % (n, sum(v) / n, v[int(n * .99)], v[-1]) if n else "-"


for name, path in (("A", sys.argv[1]), ("B", sys.argv[2])):
    allv = T[name]["k"] + T[name]["o"]
    print("%s %-26s all %s | kick %s | off %.3f" % (name, os.path.basename(path), st(allv), st(T[name]["k"]),
          sum(T[name]["o"]) / max(1, len(T[name]["o"]))))
print("differing player-actions:", diff, " score", env.score)
