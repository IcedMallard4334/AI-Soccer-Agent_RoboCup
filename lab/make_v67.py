"""Builds lab/teams/v67.py from v66: plan2.md R1, counter-window attack,
behind a switch (cw_on 0 by default, so v67 == v66).

Window: we won the ball (controlling team turned to us) within cw_ticks,
and their four outfielders average more than cw_depth from their own goal
(caught upfield). In the window cw_mode is applied through the existing
game-mode parameter cache: shoot from further out, value forward ground
more (xt_scale up) and losing the ball less (lose_pen down), and search
fewer kicks (the answer is usually "forward, now").
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v66.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


rep('name = "v66"', 'name = "v67"')
rep('version = "66"', 'version = "67"')
rep('''    "wall_on": 0,''', '''    "wall_on": 0,
    "cw_on": 0,
    "cw_ticks": 150,
    "cw_depth": 45.0,
    "cw_mode": {"shot_range": 30.0, "goal_bias": 1.0, "xt_scale": 3.5, "lose_pen": 0.04,
                "max_evals": 16},''')
rep('''        self.plan_cache = None   # (tick, ball points, their_kickoff, targets)''',
    '''        self.plan_cache = None   # (tick, ball points, their_kickoff, targets)
        self.regain_tick = -1000  # tick we last won the ball
        self.last_ctl = None''')
rep('''        if dom or bus or late:
            key = (dom, bus, late)''', '''        cw = False
        if bp["cw_on"]:
            ctl = obs.ball.controlling_team
            if ctl == 0 and self.last_ctl == 1:
                self.regain_tick = obs.tick
            self.last_ctl = ctl
            if ctl == 0 and obs.tick - self.regain_tick < bp["cw_ticks"]:
                dsum = 0.0
                for q in obs.opponents[1:]:
                    dsum += XL - q.position[0]
                cw = dsum / 4.0 > bp["cw_depth"]
        if dom or bus or late or cw:
            key = (dom, bus, late, cw)''')
rep('''                if bus:
                    mp.update(bp["bus_mode"])''', '''                if bus:
                    mp.update(bp["bus_mode"])
                if cw:
                    mp.update(bp["cw_mode"])''')
open(os.path.join(HERE, "teams", "v67.py"), "w").write(s)
print("ok")
