"""Builds lab/teams/v61.py from v60: kickoff set play (plan.md C4).

Defaults are cand59's settings (keep-model speed terms off). Switch:
* ko_on = 1: while our own kickoff is live (ball still dead on the spot),
  the players who are neither taking it nor in goal sprint to fixed spots
  (ko_spots, in attacking frame; y mirrored to the side the taker comes
  from when ko_mirror), so that the taker's first kick finds runners
  already ahead of the opponents' wide default shape.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v60.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


s = ('"""v61: v60 with cand59 defaults and a switchable kickoff set play.\n\n' + s[3:])
rep('name = "v60"', 'name = "v61"')
rep('version = "60"', 'version = "61"')
rep('''    "keep_s4": 1.0,''', '''    "keep_s4": 0.0,''')
rep('''    "keep_s6": 1.0,''', '''    "keep_s6": 0.0,
    "ko_on": 0,
    "ko_spots": ((8.0, -10.0), (8.0, 10.0), (-12.0, 0.0)),
    "ko_mirror": 1,''')
rep('''        if not kicked and gside != -1 and len(tg) == len(mine) - 1:
            self.plan_cache = (tick, pts, their_kickoff, tg)
        if their_kickoff:
            self.keep_out(actions, mine)
        return actions''', '''        if (p["ko_on"] and self.restart is not None and self.restart[1] == 0
                and abs(bx) < 0.05 and abs(by) < 0.05 and abs(bvx) + abs(bvy) < 0.05):
            self.kickoff_runs(actions, rest, chaser)
            tg = []
        if not kicked and gside != -1 and len(tg) == len(mine) - 1:
            self.plan_cache = (tick, pts, their_kickoff, tg)
        if their_kickoff:
            self.keep_out(actions, mine)
        return actions

    def kickoff_runs(self, actions, rest, taker):
        """Our kickoff, ball still on the spot: everyone not taking it or in
        goal sprints to a set-play spot (nearest-first assignment)."""
        p = self.p
        sgn = 1.0
        if p["ko_mirror"] and taker is not None and taker.y < 0.0:
            sgn = -1.0
        spots = [(x, y * sgn) for x, y in p["ko_spots"]]
        free = [b for b in rest if taker is None or b.id != taker.id]
        for sx, sy in spots:
            if not free:
                break
            b = min(free, key=lambda q: (q.x - sx) ** 2 + (q.y - sy) ** 2)
            free.remove(b)
            actions.set(b.id, PlayerAction(movement=drive(b, sx, sy, 100.0)))''')
open(os.path.join(HERE, "teams", "v61.py"), "w").write(s)
print("ok")
