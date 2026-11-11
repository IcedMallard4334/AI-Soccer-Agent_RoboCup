"""Builds lab/teams/v66.py from lab/cand65.py: plan2.md item W, "wall when
leading", behind switches (wall_on 0 by default, so v66 == cand65).

When active (we lead by at least wall_min_lead, and a one-goal lead only
once time_remaining < wall_late; never while our own kickoff is live):
* the four outfielders stand on our goal line (x = -48.5) at y = c +
  (-5.7, -1.9, +1.9, +5.7), c = clamp(0.14 * ball y, -3, 3), matched to the
  slots by their y order; nobody chases;
* the keeper stands 4 off the line, y = clamp(0.25 * ball y, -5, 5), and
  uses the usual shot-stopping move when the ball is heading into our goal;
* whoever can kick: wall_kick 0 clears at full power to the first of
  (+30, side), (+30, -side), (+45, 0) with no opponent within 2.5 of the
  lane; wall_kick 1 uses the normal kick search capped at wall_evals.
This skips the interception scans, pitch control and (with wall_kick 0)
the kick search, so walled ticks are cheap.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "cand65.py")).read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new, count)


rep('name = "Victor_Hyginus"', 'name = "v66"')
rep('version = "65"', 'version = "66"')
rep('''    "ko_on": 0,''', '''    "ko_on": 0,
    "wall_on": 0,
    "wall_min_lead": 1,
    "wall_late": 1.01,
    "wall_kick": 0,
    "wall_evals": 8,''')
rep('''        self.update_restart(obs)
        their_kickoff = self.restart is not None and self.restart[1] == 1
        if bp["reuse_k"] > 1:''', '''        self.update_restart(obs)
        their_kickoff = self.restart is not None and self.restart[1] == 1
        if bp["wall_on"]:
            lead = sg - so
            our_kickoff = self.restart is not None and self.restart[1] == 0
            if (lead >= bp["wall_min_lead"] and not our_kickoff
                    and (lead >= 2 or obs.time_remaining < bp["wall_late"])):
                self.plan_cache = None
                return self.wall(obs, mine, bx, by, bvx, bvy, their_kickoff)
        if bp["reuse_k"] > 1:''')
rep('''    def reuse_plan(self, obs, mine, bx, by, tick, their_kickoff):''', '''    def wall(self, obs, mine, bx, by, bvx, bvy, their_kickoff):
        """Lead protection: four on the goal line, keeper in front, clear."""
        p = self.p
        actions = TeamAction()
        used = set()
        # Whoever can kick this tick (or after this tick's move) plays it.
        lim = (KR - 0.05) ** 2
        for b in sorted(mine, key=lambda q: (q.x - bx) ** 2 + (q.y - by) ** 2):
            if b.cd > 0:
                continue
            kmove = None
            if not obs.can_kick(b.id):
                mx, my = drive(b, bx, by, 100.0)
                nx, ny = after_move(b, mx, my)
                if (nx - bx) ** 2 + (ny - by) ** 2 > lim:
                    continue
                kmove = (mx, my)
            if p["wall_kick"]:
                theirs = [Body(q) for q in obs.opponents]
                saved = p["max_evals"]
                self.p = dict(p)
                self.p["max_evals"] = p["wall_evals"]
                self.chosen_feat = None
                actions.set(b.id, self.choose_kick(b, kmove, mine, theirs, bx, by, bvx, bvy))
                self.p = p
            else:
                actions.set(b.id, self.wall_clear(obs, b, kmove, bx, by, bvx, bvy))
            used.add(b.id)
            break
        # Keeper: 4 off the line on the ball's side; save mode for shots.
        if 0 not in used:
            k = mine[0]
            mv = None
            if bvx < -1.0:
                pts, gtick, gside = ball_path(bx, by, bvx, bvy, HORIZON)
                if gside == -1 and gtick is not None:
                    mv = self.keeper_move(k, bx, by, pts, gtick, gside)
            if mv is None:
                mv = drive(k, -XL + 4.0, clampf(by * 0.25, -5.0, 5.0), 3.0)
            actions.set(0, PlayerAction(movement=mv))
        # Outfielders: the goal line, matched to slots in y order.
        c = clampf(0.14 * by, -3.0, 3.0)
        slots = [(-48.5, c + d) for d in (-5.7, -1.9, 1.9, 5.7)]
        field = sorted((b for b in mine[1:] if b.id not in used), key=lambda q: q.y)
        if len(field) < 4:
            # One of them is kicking: drop the slot nearest to him.
            kb = [b for b in mine[1:] if b.id in used]
            if kb:
                kb = kb[0]
                slots.remove(min(slots, key=lambda sl: (sl[0] - kb.x) ** 2 + (sl[1] - kb.y) ** 2))
        for b, (sx, sy) in zip(field, slots):
            actions.set(b.id, PlayerAction(movement=drive(b, sx, sy, 2.5)))
        if their_kickoff:
            self.keep_out(actions, mine)
        return actions

    def wall_clear(self, obs, k, kmove, bx, by, bvx, bvy):
        """Full-power clearance to the first open lane."""
        side = 1.0 if by >= 0.0 else -1.0
        opps = [o.position for o in obs.opponents]
        pick = None
        for tx, ty in ((30.0, 27.0 * side), (30.0, -27.0 * side), (45.0, 0.0)):
            dx, dy = tx - bx, ty - by
            L = math.hypot(dx, dy) or 1.0
            ux, uy = dx / L, dy / L
            ok = True
            for ox, oy in opps:
                u = (ox - bx) * ux + (oy - by) * uy
                if 0.0 < u < L and abs((ox - bx) * uy - (oy - by) * ux) < 2.5:
                    ok = False
                    break
            if ok:
                pick = (ux, uy)
                break
        if pick is None:
            dx, dy = 30.0 - bx, 27.0 * side - by
            L = math.hypot(dx, dy) or 1.0
            pick = (dx / L, dy / L)
        kk = self.kick_for(bvx, bvy, pick[0], pick[1], BALL_CAP)
        if kk is None:
            kx, ky, pw = pick[0], pick[1], 1.0
        else:
            kx, ky, pw = kk[0], kk[1], kk[2]
        mv = kmove
        if mv is None:
            mv = drive(k, bx, by, 100.0)
        return PlayerAction(movement=mv, kick_direction=(kx, ky), kick_power=pw)

    def reuse_plan(self, obs, mine, bx, by, tick, their_kickoff):''')
open(os.path.join(HERE, "teams", "v66.py"), "w").write(s)
print("ok")
