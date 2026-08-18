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

    LOOK_RANGE = 0.42  # max free-look pan, as a fraction of the screen
    LOOK_RETURN = 7.0  # how fast the view springs back once you let go

    def __init__(self):
        self.pos = pygame.Vector2(0, 0)
        self.shake_time = 0.0
        self.shake_power = 0.0
        self._offset = pygame.Vector2(0, 0)
        self.enable_shake = True
        # Free-look: a pan away from the followed target, driven by the
        # camera pad on touch. Stored as a -1..1 vector so it survives a
        # resolution change, and converted to pixels in to_screen().
        self.look = pygame.Vector2(0, 0)
        self._look_target = pygame.Vector2(0, 0)

    def set_look(self, vector):
        """Request a free-look pan. (0, 0) lets the view spring back."""
        if vector is None:
            self._look_target.update(0, 0)
            return
        x, y = vector[0], vector[1]
        self._look_target.update(clamp(x, -1.0, 1.0), clamp(y, -1.0, 1.0))

    @property
    def look_pixels(self):
        return pygame.Vector2(
            self.look.x * constants.WIDTH * self.LOOK_RANGE,
            self.look.y * constants.HEIGHT * self.LOOK_RANGE,
        )

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
        # Same exponential smoothing as follow(): the pan eases toward
        # whatever the pad is asking for, and back to centre when it lets go,
        # so a released finger never snaps the whole city sideways.
        t = 1.0 - pow(0.5, self.LOOK_RETURN * dt)
        self.look += (self._look_target - self.look) * t

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
        look = self.look_pixels
        return (
            world_x - self.pos.x + constants.WIDTH * 0.5 + self._offset.x - look.x,
            world_y - self.pos.y + constants.HEIGHT * 0.5 - altitude * constants.Z_SCALE + self._offset.y - look.y,
        )

    def is_visible(self, world_x, world_y, margin=320.0):
        """Cheap cull so off-screen buildings/enemies cost nothing to draw."""
        look = self.look_pixels
        dx = abs(world_x - self.pos.x - look.x)
        dy = abs(world_y - self.pos.y - look.y)
        return dx < constants.WIDTH * 0.5 + margin and dy < constants.HEIGHT * 0.5 + margin
