import pygame

from .. import constants
from .base import draw_shadow

GRAVITY = 260.0


class Projectile:
    """Bombs and rockets share one class; `kind` picks the flight model.

    bomb   - inherits the launching drone's horizontal velocity and falls under
             gravity, so bombing runs need altitude and lead
    rocket - flies flat and fast along the launch heading
    """

    def __init__(self, kind, pos, altitude, velocity, blast_radius, blast_damage, friendly=True):
        self.kind = kind
        self.pos = pygame.Vector2(pos)
        self.altitude = float(altitude)
        self.vel = pygame.Vector2(velocity)
        self.vertical_speed = 0.0
        self.blast_radius = blast_radius
        self.blast_damage = blast_damage
        self.friendly = friendly
        self.alive = True
        self.life = 6.0

    def update(self, dt, buildings):
        if not self.alive:
            return None

        self.life -= dt
        if self.life <= 0.0:
            self.alive = False
            return self._detonation()

        if self.kind == "bomb":
            self.vertical_speed -= GRAVITY * dt
        self.altitude += self.vertical_speed * dt
        self.pos += self.vel * dt

        if self.altitude <= 0.0:
            self.altitude = 0.0
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
