"""Builds lab/teams/v63.py from v62: deep-block signal (plan.md 23).

Defaults are cand62's settings (det_on 1, press response off). Switch:
* blk_on = 1: while we have the ball, EMA (blk_ema) of the x of their
  second-nearest outfielder to our goal (blk_mean 1; a mid-block leaves our
  half to us); when it is past blk_x, and the opponent is neither a
  dribbler nor a bus, apply blk_mode. blk_mean 0: EMA of the indicator
  "past blk_x" against blk_level instead.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v62.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


s = ('"""v63: v62 (cand62 defaults) plus a switchable deep-block signal.\n\n' + s[3:])
rep('name = "v62"', 'name = "v63"')
rep('version = "62"', 'version = "63"')
rep('''    "det_on": 0,''', '''    "det_on": 1,
    "blk_on": 0,
    "blk_x": 8.0,
    "blk_ema": 0.01,
    "blk_level": 0.5,
    "blk_mean": 1,
    "blk_mode": {"sd_on": 0, "c_drib_n": 4, "c_vends": (12.0,), "c_through": (14.0,),
                 "c_leads": (0.0, 1.2)},''')
rep('''    "press_on": 0.3,''', '''    "press_on": 2.0,''')
rep('''        self.press = 0.0         # EMA of "they press us in our half"''',
    '''        self.press = 0.0         # EMA of "they press us in our half"
        self.blk = 0.0           # EMA of "they sit in a block in their half"''')
rep('''            press = (not dribbler and not bus and self.press >= bp["press_on"])''',
    '''            press = (not dribbler and not bus and self.press >= bp["press_on"])
            if bp["blk_on"] and obs.ball.controlling_team == 0:
                xs = sorted(q.position[0] for q in obs.opponents[1:])
                if bp["blk_mean"]:
                    ind = xs[1] if len(xs) > 1 else 0.0
                else:
                    ind = 1.0 if len(xs) > 1 and xs[1] >= bp["blk_x"] else 0.0
                self.blk += (ind - self.blk) * bp["blk_ema"]
            lvl = bp["blk_x"] if bp["blk_mean"] else bp["blk_level"]
            block = (bp["blk_on"] and not dribbler and not bus and not press
                     and self.blk >= lvl)''')
rep('''            m = "dribbler" if dribbler else "bus" if bus else "press" if press else "none"''',
    '''            m = ("dribbler" if dribbler else "bus" if bus else "press" if press
                 else "block" if block else "none")''')
rep('''        press = False
        if bp["det_on"]:''', '''        press = False
        block = False
        if bp["det_on"]:''')
rep('''        if dom or bus or press or late:
            key = (dom, bus, press, late)''', '''        if dom or bus or press or block or late:
            key = (dom, bus, press, block, late)''')
rep('''                if press:
                    mp.update(bp["press_mode"])''', '''                if press:
                    mp.update(bp["press_mode"])
                if block:
                    mp.update(bp["blk_mode"])''')
open(os.path.join(HERE, "teams", "v63.py"), "w").write(s)
print("ok")
