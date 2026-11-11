"""Builds lab/cand65.py: cand59's decisions (v61 with its switches at cand59
values) plus
* the keeper-spot table filled once when the team is created, instead of
  during the match (identical values, so identical decisions; saves the
  ~1,240 exact keeper-spot searches each match used to pay inside act);
* (the kickoff set play stays off: in paired full matches it cost goal
  difference).
Docstring and name from my-team's cand59.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v61.py")).read()
cur = open(os.path.join(HERE, "submitted_c59.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


doc = cur[:cur.index('"""', 3) + 3]
s = doc + s[s.index('"""', 3) + 3:]
rep('name = "v61"', 'name = "Victor_Hyginus"')
rep('version = "61"', 'version = "65"')
# Kickoff play left off: paired full matches -0.03 +- 0.08 points, goal
# difference -0.12 +- 0.07.
rep('''    def __init__(self):
        self.p = dict(P)
        self.base_p = self.p
        self._reset_state()''', '''    def __init__(self):
        self.p = dict(P)
        self.base_p = self.p
        self._reset_state()
        if self.p["gk_table"] and not _GK:
            # Fill the keeper-spot table once, here, rather than inside act.
            for i in range(101):
                for j in range(31):
                    _GK[(i, j)] = self.keeper_spot_exact(i - 50.0, float(j))''')
open(os.path.join(HERE, "cand65.py"), "w").write(s)
print("ok")
