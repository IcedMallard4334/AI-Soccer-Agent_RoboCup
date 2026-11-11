"""Sparring archetype: park the bus. Everyone defends the goal mouth and
clears the ball as hard as possible when it comes near."""

import math

from soccer import PlayerAction, TeamAction, TeamController


class Bus(TeamController):
    name = "bus"

    def initial_formation(self, field):
        return [(-49, 0), (-44, -6), (-44, -2), (-44, 2), (-44, 6)]

    def act(self, obs):
        a = TeamAction()
        bx, by = obs.ball.position
        # Line between ball and goal centre; spread defenders across it.
        gx = -50.0
        dx, dy = bx - gx, by
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        px, py = -uy, ux
        depth = min(7.0, d * 0.5)
        offsets = [0.0, -4.5, -1.5, 1.5, 4.5]
        for p in obs.my_players:
            x, y = p.position
            if obs.can_kick(p.id):
                kx, ky = 1.0, (0.6 if y < 0 else -0.6)
                a.set(p.id, PlayerAction(movement=(0, 0), kick_direction=(kx, ky), kick_power=1.0))
                continue
            if p.id == 0:
                tx, ty = gx + ux * 1.5, max(-6.0, min(6.0, uy * 1.5 + by * 0.1))
            else:
                o = offsets[p.id]
                tx = gx + ux * depth + px * o
                ty = uy * depth + py * o
                if math.hypot(bx - x, by - y) < 5 and bx < -30:
                    tx, ty = bx, by
            mx, my = tx - x, ty - y
            m = math.hypot(mx, my)
            s = 1.0 if m > 1 else m
            a.set(p.id, PlayerAction(movement=(mx / (m or 1) * s, my / (m or 1) * s)))
        return a
