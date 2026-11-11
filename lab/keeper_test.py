"""Shoot at our keeper with the exact physics model and count saves."""
import math, sys
sys.path.insert(0, 'lab/teams'); sys.path.insert(0, '.')
sys.path.insert(0, r'C:\Users\Admin\AppData\Local\Temp\claude\C--Users-Admin-OneDrive-Desktop-Soccer-Team-soccer-student-0-1-0\04e068c0-d30c-46dd-acac-2b4225510bc4\scratchpad\physics')
import bootstrap; bootstrap.ensure_engine()
import importlib
import engine_model as em

mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else 'v9')

class B:
    def __init__(s, x, y, vx, vy, i=0):
        s.id=i; s.x=x; s.y=y; s.vx=vx; s.vy=vy; s.cd=0

def trial(team, sx, sy, gy, speed, settle=40):
    # keeper settles at its spot for the shooter position, then the shot.
    k = [-48.5, 0.0, 0.0, 0.0, 0]
    team.threat = (sx, sy)
    for _ in range(settle):
        kb = B(*k[:4])
        pts, gt, gs = mod.ball_path(sx, sy, 0, 0, 2)
        mv = team.keeper_move(kb, sx, sy, pts or [(sx, sy)], None, 0)
        k[2], k[3] = k[2]*0.9 + mv[0], k[3]*0.9 + mv[1]
        s = math.hypot(k[2], k[3])
        if s > 8: k[2] *= 8/s; k[3] *= 8/s
        k[0] += k[2]*0.05; k[1] += k[3]*0.05
    d = math.hypot(-50 - sx, gy - sy)
    ball = [sx, sy, (-50 - sx)/d*speed, (gy - sy)/d*speed]
    start = (k[0], k[1])
    for t in range(80):
        kb = B(*k[:4])
        team.threat = (ball[0], ball[1])
        pts, gt, gs = mod.ball_path(ball[0], ball[1], ball[2], ball[3], 80)
        mv = team.keeper_move(kb, ball[0], ball[1], pts, gt, gs)
        players = [list(k)]
        acts = [(mv, None, 0.0)]
        # keeper kicks if it can
        if math.hypot(ball[0]-k[0], ball[1]-k[1]) < 2.2:
            return 'save', start
        players, ball, goal, res = em.full_step(players, ball, acts)
        k = players[0]
        if goal is not None:
            return 'goal', start
        if ball[2] > 0:
            return 'save', start
    return 'save', start

team = mod.MyTeam(); team.p['gk_speed']=30; team.p['gk_max']=4
tot = 0; goals = 0
for sx, sy in [(-28, 0), (-30, 8), (-30, -12), (-35, 5), (-35, 15), (-38, -3), (-40, 10), (-25, 5), (-22, 0)]:
    row = []
    for gy in (-6.5, -4, 0, 4, 6.5):
        for sp in (22, 28):
            r, st = trial(team, sx, sy, gy, sp)
            tot += 1; goals += r == 'goal'
            row.append('G' if r == 'goal' else '.')
    print((sx, sy), 'keeper at', tuple(round(c, 1) for c in st), ''.join(row))
print('goals', goals, '/', tot)
