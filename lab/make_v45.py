"""Builds lab/teams/v45.py from v41: keep/goal probabilities behind methods,
plus optional logging of chosen kicks (features + outcome) with exploration."""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, "teams", "v41.py")
dst = os.path.join(HERE, "teams", "v45.py")
s = open(src).read()


def rep(old, new, count=1):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, count)


s = ('"""v45: v41 with the keep and goal probabilities behind keep_prob/goal_prob\n'
     '(same formulas by default) and optional logging of each chosen kick\'s\n'
     'features and outcome, with exploration, to learn those models from data.\n\n' + s[3:])
rep('name = "v41"', 'name = "v45"')
rep('version = "41"', 'version = "45"')
rep('''    "sd_shot_w": 0.85,''', '''    "sd_shot_w": 0.85,
    "log_on": 0,
    "log_eps": 0.15,''')
s = s.replace('''            q = 1.0 / (1.0 + math.exp(-(margin - p["keep_bias"]) / p["sig_keep"]))''',
              '''            q = self.keep_prob(margin, mt, math.hypot(vx, vy), mpt[0], opt is None)''')
rep('''            q = 1.0 / (1.0 + math.exp(-(margin - p["goal_bias"]) / p["sig_goal"]))
            return q * gv + (1 - q) * self.lose_value(*opt)''',
    '''            q = self.goal_prob(margin, gt, math.hypot(vx, vy), bx, by)
            return q * gv + (1 - q) * self.lose_value(*opt)''', 2)
rep('''            gv = p["xt_scale"] * p["goal_units"]
            if opt is None:
                return gv''', '''            gv = p["xt_scale"] * p["goal_units"]
            if opt is None:
                if p["log_on"]:
                    self._feat = ("g", 30.0, gt, math.hypot(vx, vy), bx, by)
                return gv''', 2)
rep('''    def shot_value_from(self, theirs, px, py, t, vix, viy):''', '''    def keep_prob(self, margin, mt, sp, rx, free):
        """Chance we keep the ball, given our reception margin over the first
        opponent (ticks), our reception tick, ball speed and reception x."""
        p = self.p
        if p["log_on"]:
            self._feat = ("k", margin, mt, sp, rx, 1.0 if free else 0.0)
        return 1.0 / (1.0 + math.exp(-(margin - p["keep_bias"]) / p["sig_keep"]))

    def goal_prob(self, margin, gt, sp, bx, by):
        """Chance a shot scores, given the first opponent's margin over the
        ball reaching the line (ticks), its travel time and speed."""
        p = self.p
        if p["log_on"]:
            self._feat = ("g", margin, gt, sp, bx, by)
        return 1.0 / (1.0 + math.exp(-(margin - p["goal_bias"]) / p["sig_goal"]))

    def shot_value_from(self, theirs, px, py, t, vix, viy):''')
rep('''            if wx and wy:
                got = memo.get((wx, wy))
                if got is None:
                    got = memo[(wx, wy)] = (self.evaluate(k, mine, theirs, bx, by, wx, wy), self._rec)
                return got
            return self.evaluate(k, mine, theirs, bx, by, wx, wy), self._rec''', '''            self._feat = None
            if wx and wy:
                got = memo.get((wx, wy))
                if got is None:
                    got = memo[(wx, wy)] = (self.evaluate(k, mine, theirs, bx, by, wx, wy), self._rec)
                    feats[(wx, wy)] = self._feat
                self._feat = feats.get((wx, wy))
                return got
            return self.evaluate(k, mine, theirs, bx, by, wx, wy), self._rec''')
rep('''        memo = {}     # ball velocity -> (value, reception info)''', '''        memo = {}     # ball velocity -> (value, reception info)
        feats = {}    # ball velocity -> features of its probability (logging)
        best_feat = None
        pool = []     # (value, action, features) for exploration when logging''')
rep('''            act = (kx, ky, pw, ux, uy, None)
            if rec is not None:
                recs.append((v, rec, act))
            if v > bestv:
                bestv = v
                best = act
                if v >= stop_v:
                    done = True''', '''            act = (kx, ky, pw, ux, uy, None)
            if rec is not None:
                recs.append((v, rec, act))
            if log_on and self._feat is not None:
                pool.append((v, act, self._feat))
            if v > bestv:
                bestv = v
                best = act
                best_feat = self._feat
                if v >= stop_v:
                    done = True''')
rep('''        def try_t(ux, uy, sp, record):
            nonlocal best, bestv, done''', '''        def try_t(ux, uy, sp, record):
            nonlocal best, bestv, done, best_feat''')
rep('''        def try_c(a, record):
            nonlocal best, bestv''', '''        def try_c(a, record):
            nonlocal best, bestv, best_feat''')
rep('''            act = (dvx / dv, dvy / dv, dv / KICK, None, None, (mvx, mvy))
            if rec is not None:
                recs.append((v, rec, act))
            if v > bestv:
                bestv = v
                best = act''', '''            act = (dvx / dv, dvy / dv, dv / KICK, None, None, (mvx, mvy))
            if rec is not None:
                recs.append((v, rec, act))
            if log_on and self._feat is not None:
                pool.append((v, act, self._feat))
            if v > bestv:
                bestv = v
                best = act
                best_feat = self._feat''')
rep('''                if v > bestv:
                    bestv = v
                    best = act
            # The strike each of the best few headings sets up at the next touch.''', '''                if v > bestv:
                    bestv = v
                    best = act
                    best_feat = None
            # The strike each of the best few headings sets up at the next touch.''')
rep('''                if sv > bestv:
                    bestv = sv
                    best = act''', '''                if sv > bestv:
                    bestv = sv
                    best = act
                    best_feat = None''')
s = s.replace('''                if v2 > bestv:
                    bestv = v2
                    best = act''', '''                if v2 > bestv:
                    bestv = v2
                    best = act
                    best_feat = None''')
rep('''        kick_for = self.kick_for
        atan2 = math.atan2''', '''        kick_for = self.kick_for
        atan2 = math.atan2
        log_on = pp["log_on"]''')
rep('''        if best is None:
            return PlayerAction(movement=kmove or (0.0, 0.0), kick_direction=(1.0, 0.0), kick_power=1.0)''', '''        if log_on and pool:
            if self.rng.random() < pp["log_eps"]:
                pool.sort(key=lambda e: -e[0])
                v0, best, best_feat = pool[self.rng.randrange(min(6, len(pool)))]
        self.chosen_feat = best_feat
        if best is None:
            return PlayerAction(movement=kmove or (0.0, 0.0), kick_direction=(1.0, 0.0), kick_power=1.0)''')
rep('''import math
import time''', '''import math
import random
import time''')
rep('''    def _reset_state(self):''', '''    def _reset_state(self):
        self.rng = random.Random(7)
        self.chosen_feat = None
        self._feat = None
        self.log_rows = []
        self.log_pending = None''')
rep('''                actions.set(kicker.id, self.choose_kick(kicker, kmove, mine, theirs,
                                                        bx, by, bvx, bvy))
                used.add(kicker.id)''', '''                self.chosen_feat = None
                actions.set(kicker.id, self.choose_kick(kicker, kmove, mine, theirs,
                                                        bx, by, bvx, bvy))
                used.add(kicker.id)
                if p["log_on"]:
                    if self.log_pending is not None and self.log_pending[0] < tick:
                        self.log_close(1.0, False)
                    if self.chosen_feat is not None:
                        self.log_pending = (tick, self.chosen_feat)''')
rep('''    def update_restart(self, obs):''', '''    def log_events(self, obs):
        pend = self.log_pending
        if pend is None:
            return
        for ev in obs.events:
            k = ev.get("kind")
            if k == "goal":
                self.log_close(1.0 if ev.get("team") == 0 else 0.0, True)
                return
            if k == "kick" and ev.get("tick", obs.tick) > pend[0]:
                self.log_close(1.0 if ev.get("team") == 0 else 0.0, False)
                return
        if obs.tick - pend[0] > 150:
            self.log_close(0.0, False)

    def log_close(self, ours, goal):
        tick, feat = self.log_pending
        self.log_pending = None
        if feat[0] == "k":
            self.log_rows.append(feat + (ours,))
        else:
            self.log_rows.append(feat + ((1.0 if (goal and ours) else 0.0),))

    def update_restart(self, obs):''')
rep('''        self.p = self.base_p
        bp = self.base_p''', '''        self.p = self.base_p
        bp = self.base_p
        if bp["log_on"]:
            self.log_events(obs)''')
open(dst, "w").write(s)
print("keep sites", s.count("self.keep_prob("), "goal sites", s.count("self.goal_prob("))
