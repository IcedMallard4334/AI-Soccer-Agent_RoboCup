"""Builds lab/teams/v54.py from v53: Phase A approximate speed work (plan.md).

* Keeper spot from a lazily filled 1-unit table (bilinear), not a search
  every tick.
* Off-ball plan re-use: on a tick where the free ball is exactly where last
  full tick predicted, nothing was kicked and none of ours can kick, every
  player keeps steering at last tick's target (for up to reuse_k - 1 ticks).
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v53.py")).read()


def rep(old, new, count=1):
    global s
    assert old in s, old[:90]
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


s = ('"""v54: v53 with a keeper-spot table and off-ball plan re-use between\n'
     'ticks where nothing has changed.\n\n' + s[3:])
rep('name = "v53"', 'name = "v54"')
rep('version = "53"', 'version = "54"')
rep('''    "kc_on": 1,''', '''    "kc_on": 1,
    "gk_table": 1,
    "reuse_k": 3,''')

# --- keeper spot table -------------------------------------------------
rep('''    def keeper_spot(self, tx, ty):
        p = self.p''', '''    def keeper_spot(self, tx, ty):
        """keeper_spot_exact, interpolated from a 1-unit grid filled lazily
        (the spot is symmetric in y)."""
        if not self.p["gk_table"]:
            return self.keeper_spot_exact(tx, ty)
        sgn = 1.0
        if ty < 0.0:
            ty = -ty
            sgn = -1.0
        fx = clampf(tx, -50.0, 50.0) + 50.0
        fy = ty if ty < 30.0 else 30.0
        i = int(fx)
        j = int(fy)
        if i > 99:
            i = 99
        if j > 29:
            j = 29
        ax = fx - i
        ay = fy - j
        tab = _GK
        c = []
        for key in ((i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)):
            v = tab.get(key)
            if v is None:
                v = tab[key] = self.keeper_spot_exact(key[0] - 50.0, float(key[1]))
            c.append(v)
        w00 = (1 - ax) * (1 - ay)
        w10 = ax * (1 - ay)
        w01 = (1 - ax) * ay
        w11 = ax * ay
        kx = c[0][0] * w00 + c[1][0] * w10 + c[2][0] * w01 + c[3][0] * w11
        ky = c[0][1] * w00 + c[1][1] * w10 + c[2][1] * w01 + c[3][1] * w11
        return kx, ky * sgn

    def keeper_spot_exact(self, tx, ty):
        p = self.p''')
rep('''_TABS = {}
''', '''_TABS = {}
_GK = {}
''')

# --- off-ball plan re-use -----------------------------------------------
rep('''        self.restart = None      # (start_tick, kicking_team, length)''',
    '''        self.restart = None      # (start_tick, kicking_team, length)
        self.plan_cache = None   # (tick, ball points, their_kickoff, targets)''')
rep('''        their_kickoff = self.restart is not None and self.restart[1] == 1

        pts, gtick, gside = ball_path(bx, by, bvx, bvy, HORIZON)''',
    '''        their_kickoff = self.restart is not None and self.restart[1] == 1
        if bp["reuse_k"] > 1:
            got = self.reuse_plan(obs, mine, bx, by, tick, their_kickoff)
            if got is not None:
                return got
        self.plan_cache = None
        tg = []
        kicked = False

        pts, gtick, gside = ball_path(bx, by, bvx, bvy, HORIZON)''')
rep('''            if kicker is not None:
                self.chosen_feat = None''', '''            if kicker is not None:
                kicked = True
                self.chosen_feat = None''')
rep('''            tx, ty = self.approach_point(chaser, ix, iy)
            actions.set(chaser.id, PlayerAction(movement=drive(chaser, tx, ty, 100.0)))''',
    '''            tx, ty = self.approach_point(chaser, ix, iy)
            actions.set(chaser.id, PlayerAction(movement=drive(chaser, tx, ty, 100.0)))
            tg.append((chaser.id, tx, ty, 100.0))''')
rep('''                b, tx, ty = got
                actions.set(b.id, PlayerAction(movement=drive(b, tx, ty, 100.0)))''',
    '''                b, tx, ty = got
                actions.set(b.id, PlayerAction(movement=drive(b, tx, ty, 100.0)))
                tg.append((b.id, tx, ty, 100.0))''')
rep('''                actions.set(cand.id, PlayerAction(movement=drive(cand, tx, ty, 100.0)))''',
    '''                actions.set(cand.id, PlayerAction(movement=drive(cand, tx, ty, 100.0)))
                tg.append((cand.id, tx, ty, 100.0))''')
rep('''            actions.set(b.id, PlayerAction(movement=drive(b, tx, ty, gain)))
        if their_kickoff:
            self.keep_out(actions, mine)
        return actions''', '''            actions.set(b.id, PlayerAction(movement=drive(b, tx, ty, gain)))
            tg.append((b.id, tx, ty, gain))
        if not kicked and gside != -1 and len(tg) == len(mine) - 1:
            self.plan_cache = (tick, pts, their_kickoff, tg)
        if their_kickoff:
            self.keep_out(actions, mine)
        return actions

    def reuse_plan(self, obs, mine, bx, by, tick, their_kickoff):
        """Last full tick's targets, if nothing has happened since that it
        did not predict; else None."""
        c = self.plan_cache
        if c is None:
            return None
        t0, pts, kickoff, targets = c
        j = tick - t0
        if j <= 0 or j >= self.base_p["reuse_k"] or j > len(pts) or kickoff != their_kickoff:
            return None
        ex, ey = pts[j - 1]
        if abs(ex - bx) > 0.05 or abs(ey - by) > 0.05:
            return None
        for ev in obs.events:
            if ev.get("kind") in ("kick", "goal", "turnover", "foul"):
                return None
        lim = (KR - 0.05) ** 2
        for b in mine:
            if b.cd > 0:
                continue
            if obs.can_kick(b.id):
                return None
            mx, my = drive(b, bx, by, 100.0)
            nx, ny = after_move(b, mx, my)
            if (nx - bx) ** 2 + (ny - by) ** 2 <= lim:
                return None
        actions = TeamAction()
        for pid, tx, ty, gain in targets:
            actions.set(pid, PlayerAction(movement=drive(mine[pid], tx, ty, gain)))
        actions.set(0, PlayerAction(movement=self.keeper_move(mine[0], bx, by, pts, None, 0)))
        if their_kickoff:
            self.keep_out(actions, mine)
        return actions''')
# --- pitch control: ball travel time inlined; re-use threshold a parameter
rep('''                tb = ball_ticks(L, 8.0 + L / ROLL) + delay''',
    '''                q = 1.0 - L / (ROLL * (8.0 + L / ROLL))
                tb = (log(q) / LNF if q > 0.0 else 999.0) + delay''')
rep('''        exp = math.exp
        opp = [(o.x, o.y, o.vx * 0.45, o.vy * 0.45) for o in theirs]''',
    '''        exp = math.exp
        log = math.log
        opp = [(o.x, o.y, o.vx * 0.45, o.vy * 0.45) for o in theirs]''')
rep('''    "pc_every": 3,''', '''    "pc_every": 6,
    "pc_move": 6.0,''')
# Production search: the fixed evaluation cap every test runs at (about
# what the ladder server affords), and a tighter wall-clock guard.
rep('''    "budget": 0.011,''', '''    "budget": 0.006,''')
rep('''    "max_evals": 100000,''', '''    "max_evals": 32,''')
rep('''                                  and abs(c[2] - hx) + abs(c[3] - hy) < 3.0))):''',
    '''                                  and abs(c[2] - hx) + abs(c[3] - hy) < p["pc_move"]))):''')

open(os.path.join(HERE, "teams", "v54.py"), "w").write(s)
print("ok")
