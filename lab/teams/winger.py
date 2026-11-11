"""Sparring archetype modelled on how the top ladder teams scored against us:
carry the ball to the byline on a wing, then pass hard across the face of
goal to a team-mate arriving at the cut-back spot, who shoots first time at
the far post."""

import math

from soccer import PlayerAction, TeamAction, TeamController


def unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-9 else (1.0, 0.0)


class Winger(TeamController):
    name = "winger"

    def reset(self, seed):
        self.restart = None

    def act(self, obs):
        a = TeamAction()
        bx, by = obs.ball.position
        bvx, bvy = obs.ball.velocity
        dead = bx == 0 and by == 0 and bvx == 0 and bvy == 0
        their_restart = dead and obs.ball.controlling_team == 1 and obs.tick % 2400 < 3000
        side = 1.0 if by >= 0 else -1.0
        cut = (37.0, -side * 4.0)        # cut-back spot
        far = (44.0, -side * 5.0)        # far post
        mates = obs.my_players
        # Who chases: the field player nearest the ball (ball a little ahead).
        px, py = bx + bvx * 0.3, by + bvy * 0.3
        field = mates[1:]
        chaser = min(field, key=lambda p: math.hypot(p.position[0] - px, p.position[1] - py))
        others = [p for p in field if p.id != chaser.id]
        others.sort(key=lambda p: p.position[0], reverse=True)
        roles = {}
        if len(others) >= 3:
            roles[others[0].id] = cut
            roles[others[1].id] = far
            roles[others[2].id] = (min(bx - 20.0, 0.0), 0.0)
        for p in mates:
            x, y = p.position
            if obs.can_kick(p.id):
                if x > 40.0 and abs(y) > 6.0:
                    # Cross to whoever is nearest the cut-back spot.
                    tgt = min((m for m in mates if m.id != p.id),
                              key=lambda m: math.hypot(m.position[0] - cut[0], m.position[1] - cut[1]))
                    tx = tgt.position[0] + tgt.velocity[0] * 0.4
                    ty = tgt.position[1] + tgt.velocity[1] * 0.4
                    kx, ky = unit(tx - bx, ty - by)
                    a.set(p.id, PlayerAction(movement=(kx, ky), kick_direction=(kx, ky), kick_power=0.85))
                elif x > 28.0 and abs(y) < 12.0:
                    gy = -6.0 if y > 0 else 6.0
                    kx, ky = unit(50.0 - bx, gy - by)
                    a.set(p.id, PlayerAction(movement=(kx, ky), kick_direction=(kx, ky), kick_power=1.0))
                else:
                    # Carry towards the corner on the ball's side.
                    gx, gy = unit(47.0 - bx, side * 20.0 - by)
                    a.set(p.id, PlayerAction(movement=(gx, gy), kick_direction=(gx, gy), kick_power=0.38))
                continue
            if p.id == 0:
                tx, ty = -48.5, max(-5.0, min(5.0, by * 0.15))
            elif p.id == chaser.id:
                tx, ty = px, py
            else:
                tx, ty = roles.get(p.id, (x, y))
            if their_restart and math.hypot(tx, ty) < 10.5:
                d = math.hypot(tx, ty) or 1.0
                tx, ty = tx / d * 10.5, ty / d * 10.5
            mx, my = unit(tx - x, ty - y)
            s = min(1.0, math.hypot(tx - x, ty - y) / 1.5)
            a.set(p.id, PlayerAction(movement=(mx * s, my * s)))
        return a
