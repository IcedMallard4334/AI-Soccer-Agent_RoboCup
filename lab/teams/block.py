"""Sparring archetype modelled on what our ladder replays show the teams that
beat or hold us doing (behaviour only): keep the ball at the feet with small
touches along whichever heading no opponent can reach before the next touch,
pass short when closed down, shoot only from inside ~24 at the corner away
from the keeper. Without the ball: keeper on the line, nearest man presses,
two hold a mid-block, one stays forward.

Variants differ only in the class attributes (lab/make_proxies.py writes
them): keepball (mid-block, line about 25-40 from our goal), block (deeper,
more cautious) and dribbler (presses high, sweeper keeper, bolder dribbling).
"""

import math

from soccer import PlayerAction, TeamAction, TeamController

DT = 0.05
F = 0.985
G5 = DT * (1 - F ** 5) / (1 - F)
KR = 2.2


def unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-9 else (1.0, 0.0)


def steer(p, tx, ty, gain=2.5):
    """Movement steering p's velocity onto one towards (tx, ty)."""
    x, y = p.position
    vx, vy = p.velocity
    dx, dy = tx - x, ty - y
    d = math.hypot(dx, dy)
    if d < 1e-6:
        mx, my = -0.9 * vx, -0.9 * vy
    else:
        s = min(8.0, gain * d)
        mx, my = dx / d * s - 0.9 * vx, dy / d * s - 0.9 * vy
    m = math.hypot(mx, my)
    if m > 1.0:
        mx, my = mx / m, my / m
    return mx, my


class KeepBall(TeamController):
    name = "block"
    LINE_BACK = 14.0       # mid-block line this far behind the ball
    LINE_MIN = -36.0       # ... but no deeper than this
    LINE_MAX = -14.0       # ... and no higher
    KEEPER_DEPTH = 1.5
    TOUCH = 9.0            # dribble touch speed
    FWD = 0.6       # weight on forward progress when dribbling
    SAFE = 1.0       # required margin (units) for a dribble heading
    SHOOT = 22.0
    PRESS2 = False         # a second man closes the carrier too

    def act(self, obs):
        a = TeamAction()
        bx, by = obs.ball.position
        bvx, bvy = obs.ball.velocity
        dead = bx == 0 and by == 0 and bvx == 0 and bvy == 0
        their_restart = dead and obs.ball.controlling_team == 1
        mates = obs.my_players
        opps = obs.opponents
        px, py = bx + bvx * 0.3, by + bvy * 0.3
        field = mates[1:]
        chaser = min(field, key=lambda p: math.hypot(p.position[0] - px, p.position[1] - py))
        ours = obs.ball.controlling_team == 0
        rest = sorted((p for p in field if p.id != chaser.id), key=lambda p: p.position[0])
        targets = {}
        if ours:
            # Spread to offer short passes: one behind, two wide, one ahead.
            spots = [(bx - 10.0, by * 0.5), (bx + 4.0, 14.0 if by < 0 else -14.0),
                     (bx + 14.0, by * 0.3)]
            for p, s in zip(rest, spots):
                targets[p.id] = (max(-40.0, min(44.0, s[0])), max(-26.0, min(26.0, s[1])))
        else:
            line = max(self.LINE_MIN, min(self.LINE_MAX, bx - self.LINE_BACK))
            spots = [(line, by * 0.4 - 7.0), (line, by * 0.4 + 7.0), (5.0, by * 0.3)]
            if self.PRESS2 and len(rest) >= 1:
                spots[0] = (px - 3.0, py)
            ys = sorted(rest[:2], key=lambda p: p.position[1]) + rest[2:]
            for p, s in zip(ys, spots):
                targets[p.id] = s
        for p in mates:
            x, y = p.position
            if obs.can_kick(p.id):
                a.set(p.id, self.on_ball(p, obs, bx, by, bvx, bvy))
                continue
            if p.id == 0:
                tx = -50.0 + self.KEEPER_DEPTH
                ty = max(-5.5, min(5.5, by * 0.35))
                if self.KEEPER_DEPTH > 3.0 and bx > -20.0:
                    tx = -50.0 + self.KEEPER_DEPTH
                if bx < -40.0 and abs(by) < 10 and math.hypot(bx - x, by - y) < 6:
                    tx, ty = px, py
                a.set(p.id, PlayerAction(movement=steer(p, tx, ty, 3.0)))
                continue
            if p.id == chaser.id:
                tx, ty = px, py
                if not ours:
                    # Come from the goal side.
                    gx, gy = unit(-50.0 - px, -py)
                    if math.hypot(x - px, y - py) > 3.0:
                        tx, ty = px + gx * 1.0, py + gy * 1.0
                gain = 100.0
            else:
                tx, ty = targets.get(p.id, (x, y))
                if not ours and math.hypot(bx - x, by - y) < 5.0:
                    tx, ty = px, py
                gain = 2.5
            if their_restart:
                gain = min(gain, 2.0)
                if math.hypot(tx, ty) < 12.5:
                    d = math.hypot(tx, ty) or 1.0
                    tx, ty = tx / d * 12.5, ty / d * 12.5
            a.set(p.id, PlayerAction(movement=steer(p, tx, ty, gain)))
        return a

    def on_ball(self, p, obs, bx, by, bvx, bvy):
        x, y = p.position
        opps = [o.position for o in obs.opponents]
        keeper = obs.opponents[0].position
        dgoal = math.hypot(50.0 - bx, by)
        if dgoal < self.SHOOT:
            gy = -5.5 if keeper[1] > 0 else 5.5
            ux, uy = unit(50.0 - bx, gy - by)
            return self.strike(p, ux, uy, 30.0, bvx, bvy)
        # Dribble headings, the safest-and-most-forward first.
        best = None
        bestv = -1e9
        for i in range(16):
            ang = i * math.pi / 8.0
            ux, uy = math.cos(ang), math.sin(ang)
            qx = bx + ux * self.TOUCH * G5
            qy = by + uy * self.TOUCH * G5
            if abs(qx) > 48.0 or abs(qy) > 28.0:
                continue
            margin = min(math.hypot(ox - qx, oy - qy) for ox, oy in opps) - 2.2 - 2.0
            if margin < self.SAFE:
                continue
            v = self.FWD * ux + 0.15 * min(margin, 6.0) - 0.02 * abs(qy)
            if v > bestv:
                bestv = v
                best = (ux, uy)
        if best is not None:
            return self.strike(p, best[0], best[1], self.TOUCH, bvx, bvy, run=True)
        # Closed down: the open team-mate with the clearest lane.
        bestm = None
        bestv = -1e9
        for m in obs.my_players[1:]:
            if m.id == p.id:
                continue
            mx, my = m.position
            L = math.hypot(mx - bx, my - by)
            if L < 4.0 or L > 30.0:
                continue
            ux, uy = (mx - bx) / L, (my - by) / L
            lane = 9.0
            for ox, oy in opps:
                u = (ox - bx) * ux + (oy - by) * uy
                if 0.0 < u < L:
                    lane = min(lane, abs((ox - bx) * uy - (oy - by) * ux) - 0.25 * u)
            v = lane + 0.05 * (mx - bx)
            if v > bestv:
                bestv = v
                bestm = (ux, uy, L)
        if bestm is not None and bestv > 0.5:
            ux, uy, L = bestm
            return self.strike(p, ux, uy, 6.0 + L / 3.3, bvx, bvy)
        ux, uy = unit(50.0 - bx, (20.0 if by > 0 else -20.0) - by)
        return self.strike(p, ux, uy, 30.0, bvx, bvy)

    @staticmethod
    def strike(p, ux, uy, speed, bvx, bvy, run=False):
        """Kick so the ball leaves along (ux, uy) at `speed` (impulse adds to
        the ball's velocity); keep moving towards the ball so the kick lands."""
        dvx, dvy = ux * speed - bvx, uy * speed - bvy
        dv = math.hypot(dvx, dvy)
        if dv < 1e-6:
            dvx, dvy, dv = ux, uy, 1.0
        pw = min(1.0, dv / 22.0)
        mv = (ux, uy) if run else (0.0, 0.0)
        return PlayerAction(movement=mv, kick_direction=(dvx / dv, dvy / dv), kick_power=pw)
