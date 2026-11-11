"""Builds lab/teams/v62.py from v61: opponent-style detection (plan.md 22).

Signals, updated every tick (cheap):
* dribbler: share of the opponent's kicks under 0.3 power (after
  det_min_kicks of them) above det_soft.
* press: EMA of "at least press_n of their outfielders are in our half while
  we have the ball in our half".
* bus: the existing deep-defenders EMA (bus_n).

Responses (det_on = 1; off by default, so v62 == v61):
* bus and not dribbler -> bus_mode plus bus_extra (direct play);
* press and not dribbler and not bus -> press_mode (counter play).
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v61.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


s = ('"""v62: v61 plus switchable opponent-style detection (det_on).\n\n' + s[3:])
rep('name = "v61"', 'name = "v62"')
rep('version = "61"', 'version = "62"')
rep('''    "ko_on": 0,''', '''    "ko_on": 0,
    "det_on": 0,
    "det_soft": 0.35,
    "det_min_kicks": 20,
    "press_n": 2.0,
    "press_ema": 0.01,
    "press_on": 0.3,
    "bus_extra": {"sd_on": 0, "c_drib_n": 4, "c_vends": (12.0,), "c_through": (14.0,),
                  "c_leads": (0.0, 1.2)},
    "press_mode": {"rear_depth": 30.0, "cover_dist": 20.0, "mark_goal_side": 3.0, "sd_on": 0,
                   "c_through": (16.0,), "shot_range": 30.0},''')
rep('''        self.mode_cache = {}     # (dominance, bus, late override) -> params''',
    '''        self.mode_cache = {}     # (dominance, bus, press, late override) -> params
        self.opp_kicks = 0       # opponent kicks seen, and how many were soft
        self.opp_soft = 0
        self.press = 0.0         # EMA of "they press us in our half"
        self.mode_ticks = {}     # detected-mode tick counts (diagnostics)''')
rep('''        sg, so = obs.score
        dom = self.terr >= bp["dom_on"] and sg - so <= bp["dom_lead"]
        bus = self.deep >= bp["bus_n"]''', '''        sg, so = obs.score
        dom = self.terr >= bp["dom_on"] and sg - so <= bp["dom_lead"]
        bus = self.deep >= bp["bus_n"]
        press = False
        if bp["det_on"]:
            for ev in obs.events:
                if ev.get("kind") == "kick" and ev.get("team") == 1:
                    self.opp_kicks += 1
                    if ev.get("power", 1.0) < 0.3:
                        self.opp_soft += 1
            if obs.ball.controlling_team == 0 and bx0 < 0.0:
                n_in = 0
                for q in obs.opponents[1:]:
                    if q.position[0] < 0.0:
                        n_in += 1
                self.press += ((1.0 if n_in >= bp["press_n"] else 0.0) - self.press) * bp["press_ema"]
            dribbler = (self.opp_kicks >= bp["det_min_kicks"]
                        and self.opp_soft > bp["det_soft"] * self.opp_kicks)
            if dribbler:
                bus = False
            press = (not dribbler and not bus and self.press >= bp["press_on"])
            m = "dribbler" if dribbler else "bus" if bus else "press" if press else "none"
            self.mode_ticks[m] = self.mode_ticks.get(m, 0) + 1''')
rep('''        if dom or bus or late:
            key = (dom, bus, late)
            mp = self.mode_cache.get(key)
            if mp is None:
                mp = dict(bp)
                if dom:
                    mp.update(bp["dom_mode"])
                if bus:
                    mp.update(bp["bus_mode"])''', '''        if dom or bus or press or late:
            key = (dom, bus, press, late)
            mp = self.mode_cache.get(key)
            if mp is None:
                mp = dict(bp)
                if dom:
                    mp.update(bp["dom_mode"])
                if bus:
                    mp.update(bp["bus_mode"])
                    if bp["det_on"]:
                        mp.update(bp["bus_extra"])
                if press:
                    mp.update(bp["press_mode"])''')
open(os.path.join(HERE, "teams", "v62.py"), "w").write(s)
print("ok")
