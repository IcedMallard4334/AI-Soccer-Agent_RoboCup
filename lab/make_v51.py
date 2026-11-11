"""Builds lab/teams/v51.py from v50: per-match calibration of the learned
keep model (logit shift from predicted vs actual keeps on our own kicks)."""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v50.py")).read()


def rep(old, new, count=1):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, count)


s = ('"""v51: v50 + per-match calibration of the learned keep model: compare its\n'
     'predictions on our own kicks with what happens, and shift its risk level\n'
     'to fit this opponent.\n\n' + s[3:])
rep('name = "v50"', 'name = "v51"')
rep('version = "50"', 'version = "51"')
rep('''    "learned_goal": 0,''', '''    "learned_goal": 0,
    "kc_on": 1,
    "kc_prior": 30.0,
    "kc_gain": 1.0,
    "kc_max": 1.5,''')
# Features are always recorded (cheap); exploration still needs log_on.
rep('''        p = self.p
        if p["log_on"]:
            self._feat = ("k", margin, mt, sp, rx, 1.0 if free else 0.0)''', '''        p = self.p
        self._feat = ("k", margin, mt, sp, rx, 1.0 if free else 0.0)''')
rep('''            z = (w[0] + w[1] * m + w[2] * free + w[3] * (mt if mt < 80.0 else 80.0) / 20.0
                 + w[4] * s2 + w[5] * rx / 50.0 + w[6] * m * s2)
            return 1.0 / (1.0 + math.exp(-z))''', '''            z = (w[0] + w[1] * m + w[2] * free + w[3] * (mt if mt < 80.0 else 80.0) / 20.0
                 + w[4] * s2 + w[5] * rx / 50.0 + w[6] * m * s2 + self.kc_shift)
            return 1.0 / (1.0 + math.exp(-z))''')
rep('''    def _reset_state(self):''', '''    def _reset_state(self):
        self.kc_shift = 0.0
        self.kc_n = 0.0
        self.kc_pred = 0.0
        self.kc_act = 0.0
        self.kc_pending = None''')
# After a kick: score the previous prediction if we kicked again, then record.
rep('''                if p["log_on"]:
                    if self.log_pending is not None and self.log_pending[0] < tick:''', '''                if p["kc_on"]:
                    if self.kc_pending is not None and self.kc_pending[0] < tick:
                        self.kc_record(self.kc_pending[1], 1.0)
                    f = self.chosen_feat
                    if f is not None and f[0] == "k":
                        self.kc_pending = (tick, self.keep_base(f))
                if p["log_on"]:
                    if self.log_pending is not None and self.log_pending[0] < tick:''')
rep('''        if bp["log_on"]:
            self.log_events(obs)''', '''        if bp["log_on"]:
            self.log_events(obs)
        if bp["kc_on"]:
            self.kc_events(obs)''')
rep('''    def log_events(self, obs):''', '''    def keep_base(self, f):
        """The learned keep probability without this match's shift."""
        _, margin, mt, sp, rx, free = f
        m = max(-15.0, min(15.0, margin)) / 10.0
        s2 = sp / 20.0
        w = KEEP_W
        z = (w[0] + w[1] * m + w[2] * free + w[3] * min(mt, 80.0) / 20.0
             + w[4] * s2 + w[5] * rx / 50.0 + w[6] * m * s2)
        return 1.0 / (1.0 + math.exp(-z))

    def kc_events(self, obs):
        pend = self.kc_pending
        if pend is None:
            return
        for ev in obs.events:
            k = ev.get("kind")
            if k == "goal":
                self.kc_pending = None
                return
            if k == "kick" and ev.get("tick", obs.tick) > pend[0]:
                self.kc_pending = None
                self.kc_record(pend[1], 1.0 if ev.get("team") == 0 else 0.0)
                return
        if obs.tick - pend[0] > 150:
            self.kc_pending = None

    def kc_record(self, pred, kept):
        bp = self.base_p
        self.kc_n += 1.0
        self.kc_pred += pred
        self.kc_act += kept
        n0 = bp["kc_prior"]
        pr = (self.kc_pred + n0 * 0.87) / (self.kc_n + n0)
        ac = (self.kc_act + n0 * 0.87) / (self.kc_n + n0)
        pr = min(max(pr, 0.02), 0.98)
        ac = min(max(ac, 0.02), 0.98)
        adj = (math.log(ac / (1 - ac)) - math.log(pr / (1 - pr))) * bp["kc_gain"]
        m = bp["kc_max"]
        self.kc_shift = max(-m, min(m, adj))

    def log_events(self, obs):''')
open(os.path.join(HERE, "teams", "v51.py"), "w").write(s)
print("ok")
