"""Builds lab/teams/v68.py from lab/cand66.py: plan2.md §13 speed package
and R3a, each behind a switch whose default keeps cand66's behaviour.

* S1, S2: existing parameters (reuse_k 3 -> 5, max_evals 32 -> 24,
  pc_every 6 -> 12) - no code needed.
* S3 me_own: evaluation cap when the kicker is in our own half (32 = off).
* S4 dec_t: trailing by 2+ with time_remaining below dec_t -> the cheap wall
  path (the result cannot change; 0 = off).
* R3a allin_t: trailing with time_remaining below allin_t -> keeper joins
  the attack (follows the ball, up to x = 34) and the rear supporter moves
  up (allin_mode); conceding again costs no points (0 = off).
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "cand66.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


rep('name = "Victor_Hyginus"', 'name = "v68"')
rep('version = "66"', 'version = "68"')
rep('''    "wall_on": 1,''', '''    "wall_on": 1,
    "me_own": 32,
    "dec_t": 0.0,
    "allin_t": 0.0,
    "allin_mode": {"rear_depth": 5.0},''')
rep('''        self.gk_depth = 0.0      # their keeper's distance off his line''',
    '''        self.gk_depth = 0.0      # their keeper's distance off his line
        self.allin = False       # trailing late: keeper joins the attack''')
rep('''        if dom or bus or late:
            key = (dom, bus, late)''', '''        self.allin = bp["allin_t"] > 0.0 and sg < so and obs.time_remaining < bp["allin_t"]
        allin = self.allin
        if dom or bus or late or allin:
            key = (dom, bus, late, allin)''')
rep('''                if late and bp[late]:
                    mp.update(bp[late])
                self.mode_cache[key] = mp''', '''                if late and bp[late]:
                    mp.update(bp[late])
                if allin:
                    mp.update(bp["allin_mode"])
                self.mode_cache[key] = mp''')
rep('''            if (lead >= bp["wall_min_lead"] and not our_kickoff
                    and (lead >= 2 or obs.time_remaining < bp["wall_late"])):''',
    '''            decided = (bp["dec_t"] > 0.0 and lead <= -2 and obs.time_remaining < bp["dec_t"])
            if not our_kickoff and (decided or (lead >= bp["wall_min_lead"]
                                                and (lead >= 2 or obs.time_remaining < bp["wall_late"]))):''')
rep('''    def keeper_move(self, k, bx, by, pts, gtick, gside):''', '''    def keeper_move(self, k, bx, by, pts, gtick, gside):
        if self.allin:
            return drive(k, min(bx - 8.0, 34.0), clampf(by, -10.0, 10.0), 100.0)''')
rep('''        max_evals = pp["max_evals"]
        scored = []''', '''        max_evals = pp["max_evals"]
        if bx < 0.0 and pp["me_own"] < max_evals:
            max_evals = pp["me_own"]
        scored = []''')
open(os.path.join(HERE, "teams", "v68.py"), "w").write(s)
print("ok")
