import math

import pygame

from . import constants


class Drone:
    # Arcade-style 2D flight: thrust always pushes along the current facing
    # angle (like Asteroids), rather than simulating real quadcopter physics.
    # That keeps the control scheme to three keys while still feeling like
    # momentum-based flight instead of a top-down "walk in 8 directions" game.
    THRUST_ACCEL = 420.0
    ROTATE_SPEED = 220.0  # degrees per second
    DRAG_PER_SECOND = 0.6  # fraction of velocity lost per second
    MAX_SPEED = 480.0
    SIZE = 16

    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2(0, 0)
        self.angle = -90.0  # degrees; -90 faces "up" in screen coordinates
        self.throttle = 0.0  # 0..1, for the HUD throttle bar and engine glow

    def handle_input(self, keys, dt):
        rotate_input = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            rotate_input -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            rotate_input += 1
        self.angle += rotate_input * self.ROTATE_SPEED * dt

        thrusting = keys[pygame.K_UP] or keys[pygame.K_w]
        self.throttle = 1.0 if thrusting else 0.0
        if thrusting:
            forward = pygame.Vector2(1, 0).rotate(self.angle)
            self.vel += forward * self.THRUST_ACCEL * dt

    def update(self, dt, bounds):
        # Exponential decay so drag feels consistent regardless of frame rate,
        # instead of just multiplying velocity by a fixed factor each frame.
        self.vel *= math.pow(1.0 - self.DRAG_PER_SECOND, dt)
        if self.vel.length() > self.MAX_SPEED:
            self.vel.scale_to_length(self.MAX_SPEED)

        self.pos += self.vel * dt

        width, height = bounds
        self.pos.x %= width
        self.pos.y %= height

    def draw(self, surface):
        if self.throttle > 0:
            self._draw_engine_glow(surface)

        forward = pygame.Vector2(1, 0).rotate(self.angle)
        right = pygame.Vector2(-forward.y, forward.x)
        nose = self.pos + forward * self.SIZE
        tail_left = self.pos - forward * self.SIZE * 0.7 + right * self.SIZE * 0.65
        tail_right = self.pos - forward * self.SIZE * 0.7 - right * self.SIZE * 0.65

        pygame.draw.polygon(surface, constants.DRONE_COLOR, [nose, tail_left, tail_right])
        pygame.draw.polygon(surface, constants.ACCENT, [nose, tail_left, tail_right], width=2)

    def _draw_engine_glow(self, surface):
        forward = pygame.Vector2(1, 0).rotate(self.angle)
        tail = self.pos - forward * self.SIZE
        radius = 22
        glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*constants.ACCENT, 70), (radius, radius), radius)
        surface.blit(glow, (tail.x - radius, tail.y - radius))
