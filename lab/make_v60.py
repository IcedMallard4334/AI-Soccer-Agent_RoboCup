"""Builds lab/teams/v60.py from v59: receiver lookahead (plan.md 17, step 3c).

Found while building it: the existing shot lookahead for receivers (la_k)
only runs when the search finished below its evaluation cap, i.e. almost
never at max_evals 32. Switches (defaults keep v59's behaviour):

* la_free = 1: run that lookahead whenever there is time left (it has its
  own small cost: la_k shot checks), not only under the evaluation cap.
* lb_k > 0: for the lb_k best kicks that keep the ball, also value the
  receiver's best follow-up: a pass to each team-mate and four forward
  carries, evaluated with our own evaluator from the reception point, with
  team-mates drifting on their velocity and opponents closing in on the
  reception point. Kept value = max(position value, la_w * shot,
  lb_w * best follow-up).
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v59.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


s = ('"""v60: v59 plus switches for the receiver lookahead (la_free, lb_k).\n\n' + s[3:])
rep('name = "v59"', 'name = "v60"')
rep('version = "59"', 'version = "60"')
rep('''    "keep_s4": 1.0,''', '''    "keep_s4": 1.0,
    "la_free": 0,
    "lb_k": 0,
    "lb_w": 0.9,
    "lb_close": 0.6,
    "lb_time": 0.7,''')
rep('''        if pp["la_k"] > 0 and not done:
            recs.sort(key=lambda e: -e[0])
            seen = 0
            for v, rec, act in recs:
                if seen >= pp["la_k"] or over():
                    break
                q, mpt, mt, vix, viy = rec
                if mpt[0] < pp["la_x"]:
                    continue
                seen += 1
                sv = self.shot_value_from(theirs, mpt[0], mpt[1], mt, vix, viy)
                keep = max(self.pos_value(*mpt), pp["la_w"] * sv)''', '''        free_la = pp["la_free"] or pp["lb_k"] > 0
        if pp["la_k"] > 0 and (not done or free_la):
            recs.sort(key=lambda e: -e[0])
            seen = 0
            lb_left = int(pp["lb_k"])
            t_lim = budget * pp["lb_time"]
            for v, rec, act in recs:
                if seen >= max(pp["la_k"], lb_left):
                    break
                if (over() and not free_la) or perf() - t0 > t_lim:
                    break
                q, mpt, mt, vix, viy = rec
                if mpt[0] < pp["la_x"] and lb_left <= 0:
                    continue
                seen += 1
                keep = self.pos_value(*mpt)
                if mpt[0] >= pp["la_x"]:
                    sv = self.shot_value_from(theirs, mpt[0], mpt[1], mt, vix, viy)
                    keep = max(keep, pp["la_w"] * sv)
                if lb_left > 0:
                    lb_left -= 1
                    fv = self.followup_value(k, mine, theirs, mpt, mt, vix, viy)
                    keep = max(keep, pp["lb_w"] * fv)''')
rep('''    def shot_value_from(self, theirs, px, py, t, vix, viy):''', '''    def followup_value(self, k, mine, theirs, mpt, mt, vix, viy):
        """Best value of the receiver's next kick from the reception point
        mpt (reached at tick mt with velocity (vix, viy)): passes to each
        team-mate and four forward carries, with team-mates drifting and
        opponents closing in. Restores the evaluator's player tuples."""
        p = self.p
        px, py = mpt
        n = int(mt) if mt < NMAX else NMAX
        close = p["lb_close"] * SPD[n]
        recv = None
        rd = 1e9
        for b in mine:
            if b.id == k.id:
                continue
            d = (b.x - px) ** 2 + (b.y - py) ** 2
            if d < rd:
                rd, recv = d, b
        if recv is None:
            return -1.0
        saved = (self._theirs_t, self._mine_t)
        opp = []
        for o in theirs:
            dx, dy = px - o.x, py - o.y
            d = math.hypot(dx, dy) or 1.0
            step = min(close, max(0.0, d - 2.0))
            ox, oy = o.x + dx / d * step, o.y + dy / d * step
            opp.append((ox, oy, dx / d * 4.0, dy / d * 4.0, 1.8, o.id, 0))
        mates = []
        a = AD[n]
        for b in mine:
            if b.id == recv.id:
                mates.append((px, py, 0.0, 0.0, 0.0, b.id, 5))
            else:
                mates.append((clampf(b.x + b.vx * a, -PXM, PXM), clampf(b.y + b.vy * a, -PYM, PYM),
                              b.vx, b.vy, b.drift, b.id, 0))
        mates.sort(key=lambda t: (t[0] - px) ** 2 + (t[1] - py) ** 2)
        opp.sort(key=lambda t: (t[0] - px) ** 2 + (t[1] - py) ** 2)
        self._theirs_t, self._mine_t = opp, mates
        best = -1e9
        cands = []
        for t in mates:
            if t[5] == recv.id:
                continue
            dx, dy = t[0] - px, t[1] - py
            d = math.hypot(dx, dy)
            if d >= 4.0:
                cands.append((dx / d, dy / d, 5.0 + d / ROLL))
        for c, s2 in fan(8)[:4]:
            cands.append((c, s2, 11.0))
        for ux, uy, sp in cands:
            kk = self.kick_for(vix, viy, ux, uy, sp)
            if kk is None:
                continue
            s3 = kk[3]
            v = self.evaluate(recv, mine, theirs, px, py, ux * s3, uy * s3)
            if v > best:
                best = v
        self._theirs_t, self._mine_t = saved
        self._rec = None
        return best

    def shot_value_from(self, theirs, px, py, t, vix, viy):''')
open(os.path.join(HERE, "teams", "v60.py"), "w").write(s)
print("ok")
