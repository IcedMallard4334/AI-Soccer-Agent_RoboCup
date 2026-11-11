"""Sparring archetype modelled on the mid-table ladder teams that hold us to
0-0: a basic keeper on the line tracking the ball sideways, two defenders
holding a line about 20 from goal and stepping out to the ball, one chaser,
one forward left high. Clears long when in trouble."""

import math

from soccer import PlayerAction, TeamAction, TeamController


def unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-9 else (1.0, 0.0)


class MidTable(TeamController):
    name = "midtable"

    def act(self, obs):
        a = TeamAction()
        bx, by = obs.ball.position
        bvx, bvy = obs.ball.velocity
        dead = bx == 0 and by == 0 and bvx == 0 and bvy == 0
        their_restart = dead and obs.ball.controlling_team == 1
        px, py = bx + bvx * 0.25, by + bvy * 0.25
        mates = obs.my_players
        chaser = min(mates[1:], key=lambda p: math.hypot(p.position[0] - px, p.position[1] - py))
        line_x = max(-42.0, min(-20.0, bx - 12.0))
        defenders = sorted((p for p in mates[1:] if p.id != chaser.id), key=lambda p: p.position[0])
        roles = {}
        if len(defenders) >= 3:
            d1, d2, fw = defenders[0], defenders[1], defenders[2]
            ys = sorted([d1, d2], key=lambda p: p.position[1])
            roles[ys[0].id] = (line_x, by * 0.5 - 6.0)
            roles[ys[1].id] = (line_x, by * 0.5 + 6.0)
            roles[fw.id] = (5.0, by * 0.3)
        for p in mates:
            x, y = p.position
            if obs.can_kick(p.id):
                if x < -20.0:
                    # Clear long towards the wing on the ball's side.
                    kx, ky = unit(30.0, 20.0 if y > 0 else -20.0)
                    pw = 1.0
                elif x > 10.0:
                    kx, ky = unit(50.0 - bx, (-4.0 if y > 0 else 4.0) - by)
                    pw = 1.0
                else:
                    fwd = max(mates[1:], key=lambda m: m.position[0])
                    kx, ky = unit(fwd.position[0] + 4.0 - bx, fwd.position[1] - by)
                    pw = 0.75
                a.set(p.id, PlayerAction(movement=(kx, ky), kick_direction=(kx, ky), kick_power=pw))
                continue
            if p.id == 0:
                tx, ty = -48.5, max(-5.5, min(5.5, by * 0.4))
            elif p.id == chaser.id:
                tx, ty = px, py
            else:
                tx, ty = roles.get(p.id, (x, y))
                # Step out to a ball that comes close.
                if math.hypot(bx - x, by - y) < 6.0 and bx < -15.0:
                    tx, ty = px, py
            if their_restart and math.hypot(tx, ty) < 10.5:
                d = math.hypot(tx, ty) or 1.0
                tx, ty = tx / d * 10.5, ty / d * 10.5
            mx, my = unit(tx - x, ty - y)
            s = min(1.0, math.hypot(tx - x, ty - y) / 1.5)
            a.set(p.id, PlayerAction(movement=(mx * s, my * s)))
        return a
