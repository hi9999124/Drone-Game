import math

import pygame

from .. import constants
from ..utils import clamp
from .base import draw_shadow

GRAVITY = 260.0


class Projectile:
    """Bombs, rockets and guided missiles share one class; `kind` picks the
    flight model.

    bomb    - inherits the launching drone's horizontal velocity and falls
              under gravity, so bombing runs need altitude and lead
    rocket  - flies flat and fast along the launch heading, unguided
    missile - like a rocket, but steers toward `target` every frame at
              `turn_rate` degrees/second (a PVO SAM site's weapon) -- outrun
              or outturn it rather than out-dodge it
    """

    def __init__(
        self,
        kind,
        pos,
        altitude,
        velocity,
        blast_radius,
        blast_damage,
        friendly=True,
        target=None,
        turn_rate=0.0,
    ):
        self.kind = kind
        self.pos = pygame.Vector2(pos)
        self.altitude = float(altitude)
        self.vel = pygame.Vector2(velocity)
        self.vertical_speed = 0.0
        self.blast_radius = blast_radius
        self.blast_damage = blast_damage
        self.friendly = friendly
        self.target = target
        self.turn_rate = turn_rate
        self.alive = True
        self.life = 6.0

    def _homing_target_alive(self):
        return self.target is not None and getattr(self.target, "alive_and_well", False)

    def update(self, dt, buildings, hit_targets=None):
        if not self.alive:
            return None

        self.life -= dt
        if self.life <= 0.0:
            self.alive = False
            return self._detonation()

        if self.kind == "bomb":
            self.vertical_speed -= GRAVITY * dt
        elif self.kind == "missile" and self.turn_rate > 0.0 and self._homing_target_alive():
            to_target = pygame.Vector2(self.target.pos) - self.pos
            if to_target.length_squared() > 1e-4:
                current_angle = math.degrees(math.atan2(self.vel.y, self.vel.x))
                desired_angle = math.degrees(math.atan2(to_target.y, to_target.x))
                delta = (desired_angle - current_angle + 180.0) % 360.0 - 180.0
                max_turn = self.turn_rate * dt
                turn = clamp(delta, -max_turn, max_turn)
                speed = self.vel.length()
                self.vel = pygame.Vector2(1, 0).rotate(current_angle + turn) * speed
            self.vertical_speed = clamp((self.target.altitude - self.altitude) * 2.0, -220.0, 220.0)
        self.altitude += self.vertical_speed * dt
        self.pos += self.vel * dt

        if self.altitude <= 0.0:
            self.altitude = 0.0
            self.alive = False
            return self._detonation()

        # Direct hit on a moving target (e.g. Air Defense mode's raiders).
        # Without this, a projectile only ever detonates against a building,
        # the ground, or its own timeout -- invisible when everything you
        # shoot at is a stationary building (Strike mode), fatal when the
        # entire point is hitting something that's flying (Defense mode).
        # None by default so Strike mode's already-verified building-splash
        # behaviour is completely unaffected.
        if hit_targets:
            for entity in hit_targets:
                if not getattr(entity, "alive", True):
                    continue
                dist = (pygame.Vector2(entity.pos) - self.pos).length()
                hit_radius = getattr(entity, "radius", 15.0) + 10.0
                # Whether a weapon can threaten a target at a given altitude
                # at all is PVOTurret.detect_ceiling's job (it won't even
                # lock on, let alone fire, above that) -- this tolerance is
                # just "did the shot actually reach the target's height",
                # generous enough to cover the full realistic range (an
                # unguided round fired near ground level vs. a drone
                # spawning at 110 and climbing toward MAX_ALTITUDE=230)
                # rather than a second, stricter gate duplicating that check.
                if dist <= hit_radius and abs(entity.altitude - self.altitude) <= 180.0:
                    self.alive = False
                    return self._detonation()

        for building in buildings:
            if building.destroyed:
                continue
            # A target counts as struck by footprint alone, same rule as a
            # kamikaze ram -- otherwise a rocket fired from the cruising
            # altitude the game itself recommends (above every building's
            # roofline, including the target's) flies straight over its
            # target forever and detonates nowhere, since blocks_at() is
            # altitude-gated and nothing about a flat, fast rocket ever
            # brings it back down into that range on its own.
            if building.is_target and building.contains_point(self.pos.x, self.pos.y):
                self.alive = False
                return self._detonation()
            if building.blocks_at(self.pos.x, self.pos.y, self.altitude):
                self.alive = False
                return self._detonation()

        half = constants.WORLD_SIZE * 0.5
        if abs(self.pos.x) > half or abs(self.pos.y) > half:
            self.alive = False
        return None

    def _detonation(self):
        return {
            "pos": pygame.Vector2(self.pos),
            "altitude": self.altitude,
            "radius": self.blast_radius,
            "damage": self.blast_damage,
            "friendly": self.friendly,
        }

    def draw(self, surface, camera):
        draw_shadow(surface, camera, self.pos, self.altitude, 5)
        sx, sy = camera.to_screen(self.pos.x, self.pos.y, self.altitude)
        color = constants.WARN if self.friendly else constants.DANGER
        if self.kind == "bomb":
            pygame.draw.circle(surface, color, (int(sx), int(sy)), 5)
            pygame.draw.circle(surface, constants.TEXT_COLOR, (int(sx), int(sy)), 5, width=1)
        else:
            direction = self.vel.normalize() if self.vel.length_squared() > 0 else pygame.Vector2(1, 0)
            tail = pygame.Vector2(sx, sy) - direction * 12
            pygame.draw.line(surface, color, (sx, sy), tail, 3)


class Explosion:
    """Purely visual: damage is applied once at spawn time by the world."""

    def __init__(self, pos, altitude, radius):
        self.pos = pygame.Vector2(pos)
        self.altitude = altitude
        self.radius = radius
        self.age = 0.0
        self.duration = 0.45
        self.alive = True

    def update(self, dt):
        self.age += dt
        if self.age >= self.duration:
            self.alive = False

    def draw(self, surface, camera):
        t = self.age / self.duration
        current = self.radius * (0.35 + 0.65 * t)
        alpha = int(220 * (1.0 - t))
        sx, sy = camera.to_screen(self.pos.x, self.pos.y, self.altitude)
        size = int(current * 2)
        if size <= 0:
            return
        blast = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(blast, (255, 190, 90, alpha), (int(current), int(current)), int(current))
        pygame.draw.circle(
            blast, (255, 240, 200, alpha), (int(current), int(current)), max(1, int(current * 0.45))
        )
        surface.blit(blast, (sx - current, sy - current))
