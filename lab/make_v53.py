"""Builds lab/teams/v53.py from v51: Phase A speed work (plan.md).
Every step here is meant to be exact (checked with lab/lockstep.py)."""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "teams", "v51.py")).read()


def rep(old, new, count=1):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, count)


s = ('"""v53: v51, faster (same decisions): no dead support scoring, pitch\n'
     'control with one arrival lookup per spot, interception scans limited to\n'
     'beating the best so far, keeper spot directions computed once.\n\n' + s[3:])
rep('name = "v51"', 'name = "v53"')
rep('version = "51"', 'version = "53"')

# A1.1 score_spots is only read when pitch control is off.
rep('''        if self.sup_cache is None or tick - self.sup_tick >= p["sup_every"]:''',
    '''        if not p["pc"] and (self.sup_cache is None or tick - self.sup_tick >= p["sup_every"]):''')

# A1.3 (exact part) pitch control: the earliest defender's arrival is the
# lookup of the smallest distance (the lookup is monotonic), so one bisect per
# spot instead of one per defender; everything inlined.
old_pc = s[s.index("    def pc_assign(self, free, theirs, hx, hy):"):s.index("    def score_spots(self, theirs, hx, hy):")]
new_pc = '''    def pc_assign(self, free, theirs, hx, hy):
        """Pitch control: each supporter takes the spot where, once a pass
        from (hx, hy) arrives, he is there before any defender; weighted by
        the value of having the ball there. Spots are kept 10 apart."""
        p = self.p
        r = p["r_get"]
        sig = p["pc_sig"]
        lane_w = p["pc_lane"]
        delay = p["pc_delay"]
        sqrt = math.sqrt
        exp = math.exp
        opp = [(o.x, o.y, o.vx * 0.45, o.vy * 0.45) for o in theirs]
        spots = []
        x0 = clampf(hx - 12.0, -42.0, 38.0)
        for ix in range(9):
            sx = x0 + ix * 5.0
            if sx > 46.0:
                break
            for iy in range(9):
                sy = -24.0 + iy * 6.0
                dx, dy = sx - hx, sy - hy
                L = math.hypot(dx, dy)
                if L < 6.0:
                    continue
                tb = ball_ticks(L, 8.0 + L / ROLL) + delay
                dmin = 1e18
                lane = 10.0
                ux, uy = dx / L, dy / L
                for ox0, oy0, ax, ay in opp:
                    ex = sx - ox0 - ax
                    ey = sy - oy0 - ay
                    d2 = ex * ex + ey * ey
                    if d2 < dmin:
                        dmin = d2
                    ox, oy = ox0 - hx, oy0 - hy
                    u = ox * ux + oy * uy
                    if 0.0 < u < L:
                        m = abs(ox * uy - oy * ux) - (1.5 + 0.22 * u)
                        if m < lane:
                            lane = m
                tthem = bisect_left(DREST, sqrt(dmin) - r)
                spots.append((sx, sy, tb, tthem, self.pos_value(sx, sy) + lane_w * clampf(lane, -5.0, 5.0)))
        out = []
        chosen = []
        for b in free:
            bestv = -1e9
            bests = (b.x, b.y)
            bx0, by0 = b.x, b.y
            ax, ay = b.vx * 0.45, b.vy * 0.45
            for sx, sy, tb, tthem, v0 in spots:
                ok = True
                for cx, cy in chosen:
                    if (cx - sx) ** 2 + (cy - sy) ** 2 < 100.0:
                        ok = False
                        break
                if not ok:
                    continue
                ex = sx - bx0 - ax
                ey = sy - by0 - ay
                tus = bisect_left(DREST, sqrt(ex * ex + ey * ey) - r)
                arrive = tb if tb > tus else tus
                z = (tthem - arrive) / sig
                if z > 30.0:
                    z = 30.0
                elif z < -30.0:
                    z = -30.0
                v = v0 / (1.0 + exp(-z))
                if v > bestv:
                    bestv = v
                    bests = (sx, sy)
            chosen.append(bests)
            out.append((b, bests))
        return out

'''
s = s.replace(old_pc, new_pc)

# A1.4 Intercepts: only the earliest of each team (and the chaser's, with
# hysteresis) are read, so each scan is limited to beating the best so far.
rep('''        my_ic = {b.id: first_intercept(b, pts, r, step=bstep) for b in mine}
        opp_ic = {b.id: first_intercept(b, pts, r, step=bstep) for b in theirs}
        opp_best = 1e9
        opp_first = None
        for b in theirs:
            t = opp_ic[b.id][0]
            if t is not None and t < opp_best:
                opp_best = t
                opp_first = b

        field_players = mine[1:]
        chaser = None
        best = 1e9
        for b in field_players:
            t = my_ic[b.id][0]
            if t is None:
                continue
            if b.id == self.chaser_id:
                t -= p["hyst"]
            if t < best:
                best = t
                chaser = b
        keeper = mine[0]
        kt, kx, ky = my_ic[0]''', '''        # Only the earliest interception of each side is used (and the
        # chaser's): each scan only has to beat the best found so far.
        opp_ic = {}
        opp_best = 1e9
        opp_first = None
        for b in theirs:
            got = first_intercept(b, pts, r, 0, None if opp_first is None else opp_best, step=bstep)
            opp_ic[b.id] = got
            t = got[0]
            if t is not None and t < opp_best:
                opp_best = t
                opp_first = b

        my_ic = {}
        field_players = mine[1:]
        chaser = None
        best = 1e9
        hyst = p["hyst"]
        for b in field_players:
            h = hyst if b.id == self.chaser_id else 0.0
            got = first_intercept(b, pts, r, 0, None if chaser is None else best + h, step=bstep)
            my_ic[b.id] = got
            t = got[0]
            if t is None:
                continue
            if h:
                t -= h
            if t < best:
                best = t
                chaser = b
        keeper = mine[0]
        my_ic[0] = first_intercept(keeper, pts, r, 0, None if chaser is None else best, step=bstep)
        kt, kx, ky = my_ic[0]''')
rep('''            for b in rest:
                t = my_ic[b.id][0]
                if t is not None and t < ct:''', '''            for b in rest:
                t = first_intercept(b, pts, r, step=bstep)[0]
                if t is not None and t < ct:''')

# A1.2 (exact part) keeper_spot: the two target directions do not depend on
# the depth being tried; compute them once.
rep('''        targets = ((-XL, GH - 0.6), (-XL, -GH + 0.6))
        best = None''', '''        dirs = []
        for gx, gy in ((-XL, GH - 0.6), (-XL, -GH + 0.6)):
            lx, ly = gx - tx, gy - ty
            ll = math.hypot(lx, ly) or 1.0
            dirs.append((lx / ll, ly / ll))
        gk_r = p["gk_r"]
        best = None''')
rep('''            m = 1e9
            for gx, gy in targets:
                lx, ly = gx - tx, gy - ty
                ll = math.hypot(lx, ly) or 1.0
                lx /= ll
                ly /= ll
                along = (kx - tx) * lx + (ky - ty) * ly
                h = abs((kx - tx) * ly - (ky - ty) * lx)
                tb = ball_ticks(max(along, 0.0), sp)
                tk = rest_ticks(h - p["gk_r"]) + 1.0''', '''            m = 1e9
            for lx, ly in dirs:
                along = (kx - tx) * lx + (ky - ty) * ly
                h = abs((kx - tx) * ly - (ky - ty) * lx)
                tb = ball_ticks(max(along, 0.0), sp)
                tk = rest_ticks(h - gk_r) + 1.0''')
open(os.path.join(HERE, "teams", "v53.py"), "w").write(s)
print("ok")
