import pygame

from .. import constants
from .base import Aircraft, draw_shadow


class PlayerDrone(Aircraft):
    def __init__(self, drone_type, x, y):
        super().__init__(x, y, altitude=110.0)
        self.type = drone_type
        self.hp = drone_type.max_hp
        self.ammo = drone_type.ammo
        self.cooldown = 0.0
        self.boost_time = 0.0
        self.invulnerable = 1.2  # brief spawn protection so you can get moving
        self.diving = False

    @property
    def alive_and_well(self):
        return self.alive and self.hp > 0

    def set_input(self, thrust, reverse, left, right, ascend, descend):
        # A single axis built from two buttons: pressing both cancels out, which
        # is what makes S/Down a real brake rather than a no-op.
        self.thrust_input = (1.0 if thrust else 0.0) - (1.0 if reverse else 0.0)
        self.turn_input = (1.0 if right else 0.0) - (1.0 if left else 0.0)
        self.climb_input = (1.0 if ascend else 0.0) - (1.0 if descend else 0.0)

    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.invulnerable = max(0.0, self.invulnerable - dt)

        thrust = self.type.thrust
        turn = self.type.turn_speed
        if self.boost_time > 0.0:
            self.boost_time -= dt
            thrust *= 2.1
            if self.diving:
                # A committed dive trades nearly all steering for speed.
                turn *= 0.25
                self.climb_input = -1.0
            if self.boost_time <= 0.0:
                self.diving = False

        self.integrate(
            dt,
            thrust=thrust,
            reverse_thrust=self.type.reverse_thrust,
            turn_speed=turn,
            drag=self.type.drag,
            max_speed=self.type.max_speed * (1.9 if self.boost_time > 0 else 1.0),
            climb_speed=self.type.climb_speed,
        )

    def use_ability(self):
        """Returns a description of what to spawn, or None if not ready."""
        if self.cooldown > 0.0 or not self.alive_and_well:
            return None

        if self.type.attack == "ram":
            self.cooldown = self.type.cooldown
            self.boost_time = 1.4 if self.type.key == "shahed" else 0.7
            self.diving = self.type.key == "shahed"
            return {"kind": "boost"}

        if self.ammo <= 0:
            return None
        self.cooldown = self.type.cooldown
        self.ammo -= 1
        if self.type.attack == "bomb":
            return {"kind": "bomb"}
        return {"kind": "rocket"}

    def take_damage(self, amount):
        if self.invulnerable > 0.0:
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
        center = pygame.Vector2(sx, sy)
        forward = self.forward
        right = pygame.Vector2(-forward.y, forward.x)
        size = self.type.size

        if self.boost_time > 0.0:
            self._draw_exhaust(surface, center, forward, size)

        nose = center + forward * size * 1.25
        tail_l = center - forward * size * 0.8 + right * size * 0.72
        tail_r = center - forward * size * 0.8 - right * size * 0.72
        body = [nose, tail_l, tail_r]

        # Flash while spawn-invulnerable so the state is readable.
        if self.invulnerable > 0.0 and int(self.invulnerable * 12) % 2 == 0:
            fill = constants.TEXT_DIM
        else:
            fill = self.type.body_color

        pygame.draw.polygon(surface, fill, body)
        pygame.draw.polygon(surface, self.type.accent_color, body, width=2)

        # Rotor booms give each airframe a distinct silhouette from above.
        if self.type.attack == "bomb":
            for offset in (right * size, -right * size):
                arm_end = center + offset
                pygame.draw.line(surface, self.type.accent_color, center, arm_end, 2)
                pygame.draw.circle(surface, self.type.accent_color, (int(arm_end.x), int(arm_end.y)), 4, width=1)
        elif self.type.key == "shahed":
            wing_l = center + right * size * 1.5 - forward * size * 0.1
            wing_r = center - right * size * 1.5 - forward * size * 0.1
            pygame.draw.line(surface, self.type.accent_color, wing_l, wing_r, 3)

        self._draw_altitude_tether(surface, camera)

    def _draw_exhaust(self, surface, center, forward, size):
        tail = center - forward * size * 1.1
        radius = int(size * 1.5)
        glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*constants.WARN, 90), (radius, radius), radius)
        surface.blit(glow, (tail.x - radius, tail.y - radius))

    def _draw_altitude_tether(self, surface, camera):
        """A faint line down to the shadow -- reinforces height at a glance."""
        if self.altitude < 8:
            return
        top = camera.to_screen(self.pos.x, self.pos.y, self.altitude)
        ground = camera.to_screen(self.pos.x, self.pos.y, 0.0)
        alpha_line = pygame.Surface((3, max(1, int(ground[1] - top[1]))), pygame.SRCALPHA)
        alpha_line.fill((*self.type.accent_color, 45))
        surface.blit(alpha_line, (top[0] - 1, top[1]))
