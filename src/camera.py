import random

import pygame

from . import constants
from .utils import clamp


class Camera:
    """Follows a world position and converts world coords to screen coords.

    The projection is the whole trick behind the 2.5D look:
        screen_x = world_x - cam_x + WIDTH/2
        screen_y = world_y - cam_y + HEIGHT/2 - altitude * Z_SCALE
    Altitude only ever shifts things *up the screen*, so a drone at 200 m draws
    high above its own shadow on the ground while still occupying the same
    ground position for collision purposes.
    """

    def __init__(self):
        self.pos = pygame.Vector2(0, 0)
        self.shake_time = 0.0
        self.shake_power = 0.0
        self._offset = pygame.Vector2(0, 0)
        self.enable_shake = True

    def snap_to(self, target):
        self.pos.update(target)

    def follow(self, target, dt, stiffness=6.0):
        # Exponential smoothing: the camera covers a fixed fraction of the
        # remaining distance each second, so it eases in without ever
        # overshooting or depending on frame rate.
        t = 1.0 - pow(0.5, stiffness * dt)
        self.pos += (pygame.Vector2(target) - self.pos) * t

    def add_shake(self, power, duration=0.35):
        if not self.enable_shake:
            return
        self.shake_power = max(self.shake_power, power)
        self.shake_time = max(self.shake_time, duration)

    def update(self, dt):
        if self.shake_time > 0.0:
            self.shake_time -= dt
            falloff = clamp(self.shake_time / 0.35, 0.0, 1.0)
            magnitude = self.shake_power * falloff
            self._offset.update(
                random.uniform(-magnitude, magnitude), random.uniform(-magnitude, magnitude)
            )
        else:
            self.shake_power = 0.0
            self._offset.update(0, 0)

    def to_screen(self, world_x, world_y, altitude=0.0):
        return (
            world_x - self.pos.x + constants.WIDTH * 0.5 + self._offset.x,
            world_y - self.pos.y + constants.HEIGHT * 0.5 - altitude * constants.Z_SCALE + self._offset.y,
        )

    def is_visible(self, world_x, world_y, margin=320.0):
        """Cheap cull so off-screen buildings/enemies cost nothing to draw."""
        dx = abs(world_x - self.pos.x)
        dy = abs(world_y - self.pos.y)
        return dx < constants.WIDTH * 0.5 + margin and dy < constants.HEIGHT * 0.5 + margin
