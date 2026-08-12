import pygame

from .. import constants
from ..utils import clamp
from .base import draw_shadow


class Civilian:
    """The player's character in Survival mode: on foot, no momentum or
    facing to fight against -- direct 8-way movement, because the skill
    this mode tests is reading the map and reacting to a warning in time,
    not piloting anything. Deliberately the simplest-moving entity in the
    game; the tension comes entirely from the threat, not the controls."""

    SPEED = 230.0

    def __init__(self, x, y, max_hp=3):
        self.pos = pygame.Vector2(x, y)
        self.altitude = 0.0
        self.hp = max_hp
        self.max_hp = max_hp
        self.alive = True
        self.invulnerable = 0.0
        self._move_dir = pygame.Vector2(0, 0)
        self.facing = pygame.Vector2(0, -1)

    @property
    def alive_and_well(self):
        return self.alive and self.hp > 0

    def set_input(self, up, down, left, right):
        move = pygame.Vector2((1.0 if right else 0.0) - (1.0 if left else 0.0), (1.0 if down else 0.0) - (1.0 if up else 0.0))
        if move.length_squared() > 1e-6:
            move = move.normalize()
            self.facing = move
        self._move_dir = move

    def update(self, dt):
        self.invulnerable = max(0.0, self.invulnerable - dt)
        self.pos += self._move_dir * self.SPEED * dt
        half = constants.WORLD_SIZE * 0.5
        self.pos.x = clamp(self.pos.x, -half, half)
        self.pos.y = clamp(self.pos.y, -half, half)

    def take_damage(self, amount):
        if self.invulnerable > 0.0 or not self.alive:
            return False
        self.hp -= amount
        self.invulnerable = 1.2
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            return True
        return False

    def draw(self, surface, camera):
        draw_shadow(surface, camera, self.pos, self.altitude, 10)
        sx, sy = camera.to_screen(self.pos.x, self.pos.y, self.altitude)
        size = 10
        flash = self.invulnerable > 0.0 and int(self.invulnerable * 14) % 2 == 0
        color = constants.TEXT_DIM if flash else constants.ACCENT
        nose = pygame.Vector2(sx, sy) + self.facing * size
        left = pygame.Vector2(sx, sy) - self.facing * size * 0.6 + pygame.Vector2(-self.facing.y, self.facing.x) * size * 0.6
        right = pygame.Vector2(sx, sy) - self.facing * size * 0.6 - pygame.Vector2(-self.facing.y, self.facing.x) * size * 0.6
        pygame.draw.polygon(surface, color, [nose, left, right])
        pygame.draw.polygon(surface, constants.TEXT_COLOR, [nose, left, right], width=1)
