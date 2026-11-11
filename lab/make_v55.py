"""Builds lab/teams/v55.py from v54 with two switchable experiments (both
off by default, so v55 == v54 until a parameter turns one on):

* C3 keeper-aware shot range (shot_kd > 0): shots are searched only within
  min(shot_range, shot_r0 + shot_kd * their keeper's depth off his line).
* D1 carrier model (carrier = 1): when an opponent is about to touch the
  ball (their first touch within car_t ticks) the chaser runs at where that
  carrier will be when we can get there, car_off goal-side of him, instead
  of at the free ball's interception point.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v54.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


s = ('"""v55: v54 plus switchable experiments: keeper-aware shot range (C3)\n'
     'and a carrier model for the chaser (D1).\n\n' + s[3:])
rep('name = "v54"', 'name = "v55"')
rep('version = "54"', 'version = "55"')
rep('''    "kc_on": 1,''', '''    "kc_on": 1,
    "shot_kd": 0.0,
    "shot_r0": 24.0,
    "carrier": 0,
    "car_t": 3.0,
    "car_off": 1.5,''')
rep('''        self.plan_cache = None   # (tick, ball points, their_kickoff, targets)''',
    '''        self.plan_cache = None   # (tick, ball points, their_kickoff, targets)
        self.gk_depth = 0.0      # their keeper's distance off his line''')
rep('''        mine = [Body(q) for q in obs.my_players]
        theirs = [Body(q) for q in obs.opponents]''', '''        mine = [Body(q) for q in obs.my_players]
        theirs = [Body(q) for q in obs.opponents]
        self.gk_depth = XL - theirs[0].x''')

# C3
rep('''        shots_on = dgoal < pp["shot_range"]''', '''        rng = pp["shot_range"]
        if pp["shot_kd"] > 0.0:
            rng = min(rng, pp["shot_r0"] + pp["shot_kd"] * self.gk_depth)
        shots_on = dgoal < rng''')

# D1
rep('''            _, ix, iy = my_ic[chaser.id]
            if ix is None:
                ix, iy = bx, by
            tx, ty = self.approach_point(chaser, ix, iy)''', '''            _, ix, iy = my_ic[chaser.id]
            if ix is None:
                ix, iy = bx, by
            tx, ty = self.approach_point(chaser, ix, iy)
            if (p["carrier"] and not attacking and opp_first is not None
                    and opp_best <= p["car_t"]):
                tx, ty = self.carrier_point(chaser, opp_first)''')
rep('''    @staticmethod
    def approach_point(b, ix, iy):''', '''    def carrier_point(self, b, o):
        """Where carrier o will be when b can get there (o keeps his
        velocity), moved car_off towards our goal."""
        x, y = o.x, o.y
        for _ in range(3):
            t = reach_est(b.x, b.y, b.vx, b.vy, x, y, 0.0)
            x = clampf(o.x + o.vx * DT * t, -PXM, PXM)
            y = clampf(o.y + o.vy * DT * t, -PYM, PYM)
        gx, gy = -XL - x, -y
        gl = math.hypot(gx, gy) or 1.0
        off = self.p["car_off"]
        return x + gx / gl * off, y + gy / gl * off

    @staticmethod
    def approach_point(b, ix, iy):''')
open(os.path.join(HERE, "teams", "v55.py"), "w").write(s)
print("ok")
