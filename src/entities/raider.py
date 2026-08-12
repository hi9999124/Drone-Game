import math
import random

import pygame

from .. import constants
from .base import draw_shadow

RAIDER_PROFILES = {
    "Easy": dict(speed=170.0, hp=2.0, damage=18.0, waves=4, per_wave=3, wave_gap=6.0),
    "Normal": dict(speed=210.0, hp=2.0, damage=24.0, waves=5, per_wave=4, wave_gap=5.0),
    "Hard": dict(speed=255.0, hp=3.0, damage=30.0, waves=6, per_wave=5, wave_gap=4.0),
    "Insane": dict(speed=300.0, hp=3.0, damage=38.0, waves=7, per_wave=6, wave_gap=3.0),
}


class RaiderDrone:
    """A simple attacking BPLA: flies straight from a map edge at whichever
    protected structure is currently nearest, and detonates on contact.
    Deliberately dumber than EnemyDrone (no patrol/chase state machine,
    no evasion) -- in this mode the drone is the thing being intercepted,
    and the player's own aim is what should carry the difficulty, not AI
    trickery on the attacking side."""

    def __init__(self, x, y, profile):
        self.pos = pygame.Vector2(x, y)
        # Kept low and narrow on purpose: the flak gun's fire is unguided and
        # stays at the altitude it was fired at for its whole flight (no
        # elevation control exists for the player, only azimuth), so a
        # raider flying meaningfully higher than that would simply be
        # unhittable by flak regardless of aim. A SAM's guided missile
        # actively climbs to match its target's altitude and has no such
        # limit, but flak needing to stay a real option is the point of the
        # difficulty/loadout choice between the two units.
        self.altitude = random.uniform(20.0, 70.0)
        self.speed = profile["speed"]
        self.hp = profile["hp"]
        self.damage = profile["damage"]
        self.alive = True
        self.radius = 12.0
        self.angle = 0.0

    @property
    def alive_and_well(self):
        # Homing missiles (Projectile._homing_target_alive) duck-type against
        # this exact attribute, same as PlayerDrone -- a raider has no
        # separate "alive but disabled" state, so it's just alive.
        return self.alive

    def update(self, dt, protected):
        if not self.alive:
            return None
        live_targets = [b for b in protected if not b.destroyed]
        if not live_targets:
            return None
        target = min(live_targets, key=lambda b: (b.center - self.pos).length_squared())
        to_target = target.center - self.pos
        if to_target.length_squared() > 1:
            desired = math.degrees(math.atan2(to_target.y, to_target.x))
            self.angle = desired
        self.pos += pygame.Vector2(1, 0).rotate(self.angle) * self.speed * dt

        if target.contains_point(self.pos.x, self.pos.y):
            self.alive = False
            return {"pos": pygame.Vector2(self.pos), "altitude": self.altitude, "damage": self.damage}
        return None

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def draw(self, surface, camera):
        draw_shadow(surface, camera, self.pos, self.altitude, self.radius)
        sx, sy = camera.to_screen(self.pos.x, self.pos.y, self.altitude)
        forward = pygame.Vector2(1, 0).rotate(self.angle)
        right = pygame.Vector2(-forward.y, forward.x)
        size = self.radius
        nose = pygame.Vector2(sx, sy) + forward * size
        tail_l = pygame.Vector2(sx, sy) - forward * size * 0.7 + right * size * 0.7
        tail_r = pygame.Vector2(sx, sy) - forward * size * 0.7 - right * size * 0.7
        pygame.draw.polygon(surface, constants.ENEMY_DIM, [nose, tail_l, tail_r])
        pygame.draw.polygon(surface, constants.ENEMY_COLOR, [nose, tail_l, tail_r], width=2)
