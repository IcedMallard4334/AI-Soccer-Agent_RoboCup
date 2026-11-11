"""Builds lab/teams/v59.py from v57 (= v58's decisions): bet 6, passing.

Switches (defaults keep v58's behaviour):
* keep_s4 / keep_s6 scale the keep model's ball-speed terms (w4 * speed and
  w6 * margin * speed). With the fitted weights the margin coefficient at
  20 u/s is 0.63 - 0.74 < 0: a fast ball is judged as risky whatever its
  margin, which penalises every long pass. Fitted only on kicks the search
  already chose (selection bias, plan.md 15).
* The production guard is 12 ms (v58).
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v57.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


s = ('"""v59: v58 plus switches for the passing experiments (keep-model speed\n'
     'terms).\n\n' + s[3:])
rep('name = "v57"', 'name = "v59"')
rep('version = "57"', 'version = "59"')
rep('''    "budget": 0.006,''', '''    "budget": 0.012,''')
rep('''    "kc_on": 1,''', '''    "kc_on": 1,
    "keep_s4": 1.0,
    "keep_s6": 1.0,''')
rep('''            z = (w[0] + w[1] * m + w[2] * free + w[3] * (mt if mt < 80.0 else 80.0) / 20.0
                 + w[4] * s2 + w[5] * rx / 50.0 + w[6] * m * s2 + self.kc_shift)''',
    '''            z = (w[0] + w[1] * m + w[2] * free + w[3] * (mt if mt < 80.0 else 80.0) / 20.0
                 + w[4] * p["keep_s4"] * s2 + w[5] * rx / 50.0 + w[6] * p["keep_s6"] * m * s2
                 + self.kc_shift)''')
rep('''        z = (w[0] + w[1] * m + w[2] * free + w[3] * min(mt, 80.0) / 20.0
             + w[4] * s2 + w[5] * rx / 50.0 + w[6] * m * s2)''',
    '''        bp = self.base_p
        z = (w[0] + w[1] * m + w[2] * free + w[3] * min(mt, 80.0) / 20.0
             + w[4] * bp["keep_s4"] * s2 + w[5] * rx / 50.0 + w[6] * bp["keep_s6"] * m * s2)''')
open(os.path.join(HERE, "teams", "v59.py"), "w").write(s)
print("ok")
