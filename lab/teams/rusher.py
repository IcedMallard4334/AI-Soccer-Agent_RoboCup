"""Sparring archetype: long shooters. The nearest two chase the ball, the
rest push high, and every touch is a full-power shot at a goal corner."""

import math

from soccer import PlayerAction, TeamAction, TeamController


class Rusher(TeamController):
    name = "rusher"

    def initial_formation(self, field):
        return [(-48, 0), (-25, -12), (-25, 12), (-12, -6), (-12, 6)]

    def act(self, obs):
        a = TeamAction()
        bx, by = obs.ball.position
        order = sorted(obs.my_players[1:], key=lambda p: math.hypot(p.position[0] - bx, p.position[1] - by))
        chasers = {p.id for p in order[:2]}
        for p in obs.my_players:
            x, y = p.position
            if obs.can_kick(p.id):
                ty = 6.0 if y < 0 else -6.0
                dx, dy = 50.0 - bx, ty - by
                a.set(p.id, PlayerAction(movement=(dx, dy), kick_direction=(dx, dy), kick_power=1.0))
                continue
            if p.id == 0:
                tx, ty = -48.5, max(-6.0, min(6.0, by * 0.2))
            elif p.id in chasers:
                tx, ty = bx, by
            else:
                tx, ty = min(bx + 15, 40), (12 if p.id % 2 else -12)
            mx, my = tx - x, ty - y
            m = math.hypot(mx, my) or 1.0
            a.set(p.id, PlayerAction(movement=(mx / m, my / m)))
        return a
