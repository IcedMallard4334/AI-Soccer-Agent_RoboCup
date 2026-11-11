"""Identity check: drive one match with team A; feed the same observations to team B and compare every action."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "lab", "teams"))
import bootstrap; bootstrap.ensure_engine()
from soccer import SoccerEnv
from soccer.helpers import load_controller
a = load_controller(os.path.join(ROOT, sys.argv[1])); b = load_controller(os.path.join(ROOT, sys.argv[2]))
for t in (a, b): t.p.update(budget=1.0, max_evals=32)
seed = int(sys.argv[3])
env = SoccerEnv(per_decision_timeout_ms=1000); env.use_baseline(1, sys.argv[4] if len(sys.argv) > 4 else "elite")
env.set_formation(0, a.initial_formation(env.field)); a.reset(seed); b.reset(seed)
obs = env.reset(seed=seed, kickoff_team=0)
diff = 0; n = 0
while not env.finished:
    oa = obs["team_a"]; n += 1
    x = a.act(oa); y = b.act(oa)
    for pid in range(5):
        pa = x.players.get(pid); pb = y.players.get(pid)
        ta = (pa.movement, pa.kick_direction, pa.kick_power) if pa else None
        tb = (pb.movement, pb.kick_direction, pb.kick_power) if pb else None
        if ta != tb: diff += 1
    obs, _ = env.step({"team_a": x})
print("ticks", n, "differing player-actions", diff, "score", env.score)
