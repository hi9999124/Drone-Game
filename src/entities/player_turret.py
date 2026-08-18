import pygame

from ..utils import clamp
from .base import draw_shadow

TURN_SPEED = 130.0  # degrees/second -- deliberately slower than a drone's,
                     # a ground mount can't snap-track like an airframe can


class PlayerTurret:
    """The player's own PVO unit in Air Defense mode: stationary, aims and
    fires rather than flies. Reuses PVOUnitType stats (same flak/SAM the AI
    hazard uses in the Drone Strike mission) so both sides of "PVO vs
    drones" are balanced against the same numbers, not a separate table
    someone has to keep in sync by hand."""

    def __init__(self, x, y, unit_type, ammo):
        self.pos = pygame.Vector2(x, y)
        self.altitude = 0.0
        self.type = unit_type
        self.hp = unit_type.max_hp * 2.0  # the whole mode rests on this unit surviving; a decoy AI turret doesn't need to
        self.max_hp = self.hp
        self.alive = True
        self.angle = -90.0
        self.turn_input = 0.0
        self.cooldown = 0.0
        self.ammo = ammo
        self.max_ammo = ammo
        self._fire_requested = False

    @property
    def forward(self):
        return pygame.Vector2(1, 0).rotate(self.angle)

    @property
    def alive_and_well(self):
        return self.alive and self.hp > 0

    STICK_DEAD_ZONE = 0.18

    def set_input(self, left, right, fire, stick=None):
        self.turn_input = (1.0 if right else 0.0) - (1.0 if left else 0.0)
        if stick is not None:
            # A turret has one axis (barrel bearing), so only the stick's
            # horizontal deflection matters -- pushed right, it traverses
            # right, proportionally to how far.
            vector = pygame.Vector2(float(stick[0]), float(stick[1]))
            if vector.length() >= self.STICK_DEAD_ZONE:
                self.turn_input = clamp(vector.x, -1.0, 1.0)
        self._fire_requested = fire

    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.angle += self.turn_input * TURN_SPEED * dt

    def try_fire(self):
        """Returns a spawn spec for World to turn into a Projectile, or None."""
        if not self._fire_requested or self.cooldown > 0.0 or self.ammo <= 0 or not self.alive_and_well:
            return None
        self.cooldown = self.type.cooldown
        self.ammo -= 1
        return {
            "pos": pygame.Vector2(self.pos),
            "altitude": self.altitude + self.type.size * 0.5,
            "velocity": self.forward * self.type.projectile_speed,
            "damage": self.type.damage,
            "blast_radius": self.type.blast_radius,
            "homing": self.type.homing,
            "turn_rate": self.type.turn_rate,
        }

    def take_damage(self, amount):
        if not self.alive:
            return False
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            return True
        return False

    def draw(self, surface, camera):
        draw_shadow(surface, camera, self.pos, self.altitude, self.type.size)
        sx, sy = camera.to_screen(self.pos.x, self.pos.y, self.altitude)
        forward = self.forward
        right = pygame.Vector2(-forward.y, forward.x)
        size = self.type.size

        base = [
            (sx - size * 0.7, sy + size * 0.55),
            (sx + size * 0.7, sy + size * 0.55),
            (sx + size * 0.5, sy - size * 0.2),
            (sx - size * 0.5, sy - size * 0.2),
        ]
        pygame.draw.polygon(surface, self.type.body_color, base)
        pygame.draw.polygon(surface, self.type.accent_color, base, width=2)

        barrel_len = size * (1.6 if self.type.key == "sam" else 1.2)
        tip = pygame.Vector2(sx, sy) + forward * barrel_len - pygame.Vector2(0, size * 0.3)
        pygame.draw.line(surface, self.type.accent_color, (sx, sy - size * 0.3), tip, 5)
        _ = right  # reserved for a future twin-barrel silhouette
