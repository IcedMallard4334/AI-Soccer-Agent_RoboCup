"""Builds lab/teams/v57.py from v55 (experiments off = v54 decisions):
exact per-tick savings (bet 2, plan.md 14.3).

* Game-mode parameter dicts (dominance / bus / late-game overrides) are built
  once per combination and reused, instead of copied every tick.
* Opponent bodies are only built on ticks that are not plan re-use ticks.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v55.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


s = ('"""v57: v55 (experiments off, so v54 decisions) with game-mode parameter\n'
     'sets cached and opponent bodies built only when a plan is computed.\n\n' + s[3:])
rep('name = "v55"', 'name = "v57"')
rep('version = "55"', 'version = "57"')

rep('''        self.gk_depth = 0.0      # their keeper's distance off his line''',
    '''        self.gk_depth = 0.0      # their keeper's distance off his line
        self.mode_cache = {}     # (dominance, bus, late override) -> params''')
rep('''        sg, so = obs.score
        if self.terr >= bp["dom_on"] and sg - so <= bp["dom_lead"]:
            self.p = dict(self.p)
            self.p.update(bp["dom_mode"])
        if self.deep >= bp["bus_n"]:
            self.p = dict(self.p)
            self.p.update(bp["bus_mode"])
        if obs.time_remaining < self.base_p["gs_late"]:
            mine_g, theirs_g = obs.score
            over = None
            if mine_g <= theirs_g:
                over = self.base_p["gs_chase"]
            elif mine_g - theirs_g == 1:
                over = self.base_p["gs_protect"]
            if over:
                self.p = dict(self.p)
                self.p.update(over)
        p = self.p''', '''        sg, so = obs.score
        dom = self.terr >= bp["dom_on"] and sg - so <= bp["dom_lead"]
        bus = self.deep >= bp["bus_n"]
        late = None
        if obs.time_remaining < bp["gs_late"]:
            if sg <= so:
                late = "gs_chase"
            elif sg - so == 1:
                late = "gs_protect"
        if dom or bus or late:
            key = (dom, bus, late)
            mp = self.mode_cache.get(key)
            if mp is None:
                mp = dict(bp)
                if dom:
                    mp.update(bp["dom_mode"])
                if bus:
                    mp.update(bp["bus_mode"])
                if late and bp[late]:
                    mp.update(bp[late])
                self.mode_cache[key] = mp
            self.p = mp
        p = self.p''')
rep('''        mine = [Body(q) for q in obs.my_players]
        theirs = [Body(q) for q in obs.opponents]
        self.gk_depth = XL - theirs[0].x''', '''        mine = [Body(q) for q in obs.my_players]
        self.gk_depth = XL - obs.opponents[0].position[0]''')
rep('''            if got is not None:
                return got
        self.plan_cache = None''', '''            if got is not None:
                return got
        theirs = [Body(q) for q in obs.opponents]
        self.plan_cache = None''')
open(os.path.join(HERE, "teams", "v57.py"), "w").write(s)
print("ok")
