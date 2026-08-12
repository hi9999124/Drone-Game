import math

import pygame

from .. import constants
from ..utils import clamp


class Aircraft:
    """Shared flight state + integration for anything that flies (player, enemies).

    Keeping one implementation here is what lets a player drone and an AI drone
    obey identical physics -- the only difference between them is who sets
    `thrust_input` / `turn_input` / `climb_input` each frame.
    """

    def __init__(self, x, y, altitude=90.0, angle=-90.0):
        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2(0, 0)
        self.altitude = altitude
        self.vertical_speed = 0.0
        self.angle = angle
        self.alive = True

        # Inputs, in the range -1..1, rewritten every frame by a controller.
        self.thrust_input = 0.0
        self.turn_input = 0.0
        self.climb_input = 0.0

    @property
    def forward(self):
        return pygame.Vector2(1, 0).rotate(self.angle)

    @property
    def speed(self):
        return self.vel.length()

    def integrate(self, dt, thrust, reverse_thrust, turn_speed, drag, max_speed, climb_speed):
        self.angle += self.turn_input * turn_speed * dt

        if self.thrust_input > 0.0:
            accel = thrust * self.thrust_input
        else:
            # Reverse is deliberately weaker than forward thrust -- it reads as
            # backing off / braking rather than flying backwards at full tilt.
            accel = reverse_thrust * self.thrust_input
        if accel:
            self.vel += self.forward * accel * dt

        # Exponential drag so deceleration is frame-rate independent.
        # `drag` is meant to stay below 1.0 ("fraction of speed shed per
        # second"), but a misconfigured drone (drag >= 1.0) must not zero out
        # velocity entirely: max(0.0, 1.0 - drag) ** dt evaluates to exactly
        # 0.0 for any dt > 0 once drag >= 1.0, silently erasing all thrust
        # every frame. Clamping the retained fraction to a tiny nonzero floor
        # turns "drone physically cannot move" into "drone barely coasts",
        # which is recoverable/obviously-a-bug-looking instead of invisible.
        retained = max(1e-3, 1.0 - min(drag, 0.98))
        self.vel *= math.pow(retained, dt)
        if self.vel.length() > max_speed:
            self.vel.scale_to_length(max_speed)
        self.pos += self.vel * dt

        self.vertical_speed = self.climb_input * climb_speed
        self.altitude = clamp(
            self.altitude + self.vertical_speed * dt, 0.0, constants.MAX_ALTITUDE
        )

        half = constants.WORLD_SIZE * 0.5
        self.pos.x = clamp(self.pos.x, -half, half)
        self.pos.y = clamp(self.pos.y, -half, half)

    def distance_to(self, other):
        """3D distance, treating altitude as the third axis."""
        dx = self.pos.x - other.pos.x
        dy = self.pos.y - other.pos.y
        dz = self.altitude - other.altitude
        return math.sqrt(dx * dx + dy * dy + dz * dz)


def draw_shadow(surface, camera, world_pos, altitude, radius):
    """Ground shadow that shrinks and fades with altitude.

    This is the single most important cue for reading height in a 2.5D view --
    without it players cannot tell a high drone from a distant one.
    """
    fade = clamp(1.0 - altitude / constants.MAX_ALTITUDE, 0.15, 1.0)
    shadow_radius = max(2, int(radius * (0.45 + 0.55 * fade)))
    sx, sy = camera.to_screen(world_pos.x, world_pos.y, 0.0)
    size = shadow_radius * 2
    shadow = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.ellipse(
        shadow,
        (0, 0, 0, int(110 * fade)),
        (0, int(shadow_radius * 0.55), size, int(size * 0.62)),
    )
    surface.blit(shadow, (sx - shadow_radius, sy - shadow_radius))
