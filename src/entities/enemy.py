import math
import random

import pygame

from .. import constants
from ..utils import clamp
from .base import Aircraft, draw_shadow

# Difficulty knobs. Every tier is the same AI -- only these numbers change,
# which keeps "Insane" honest (a faster, sharper enemy) rather than a cheating one.
DIFFICULTY_PROFILES = {
    "Easy": dict(count=3, speed=0.70, damage=0.6, detect=520.0, reaction=0.85, turn=0.7, shoots=False),
    "Normal": dict(count=5, speed=0.85, damage=1.0, detect=700.0, reaction=0.45, turn=0.85, shoots=False),
    "Hard": dict(count=7, speed=1.0, damage=1.4, detect=900.0, reaction=0.25, turn=1.0, shoots=True),
    "Insane": dict(count=10, speed=1.15, damage=1.8, detect=1200.0, reaction=0.12, turn=1.15, shoots=True),
}

STATE_PATROL = "patrol"
STATE_CHASE = "chase"
STATE_ATTACK = "attack"


class EnemyDrone(Aircraft):
    BASE_SPEED = 330.0
    BASE_TURN = 150.0

    def __init__(self, x, y, profile):
        super().__init__(x, y, altitude=random.uniform(50.0, 170.0))
        self.profile = profile
        self.hp = 2.0
        self.state = STATE_PATROL
        self.reaction_timer = 0.0
        self.patrol_target = self._random_patrol_point()
        self.fire_cooldown = random.uniform(1.5, 3.5)
        self.radius = 13.0

    def _random_patrol_point(self):
        half = constants.WORLD_SIZE * 0.45
        return pygame.Vector2(random.uniform(-half, half), random.uniform(-half, half))

    def update(self, dt, player, buildings):
        if not self.alive:
            return None

        fired = None
        distance = self.distance_to(player) if player and player.alive_and_well else float("inf")
        detect = self.profile["detect"]

        if distance < detect:
            # Reaction delay before committing -- this is what makes Easy feel
            # sluggish and Insane feel like it read your mind.
            self.reaction_timer += dt
            if self.reaction_timer >= self.profile["reaction"]:
                self.state = STATE_ATTACK if distance < 260.0 else STATE_CHASE
        else:
            self.reaction_timer = 0.0
            self.state = STATE_PATROL

        if self.state == STATE_PATROL:
            self._steer_toward(self.patrol_target, 0.0, dt)
            if self.pos.distance_to(self.patrol_target) < 120.0:
                self.patrol_target = self._random_patrol_point()
        else:
            self._steer_toward(player.pos, player.altitude, dt)
            if self.profile["shoots"]:
                self.fire_cooldown -= dt
                if self.fire_cooldown <= 0.0 and distance < 620.0:
                    self.fire_cooldown = random.uniform(2.0, 3.6)
                    fired = self._make_shot()

        self.integrate(
            dt,
            thrust=self.BASE_SPEED * self.profile["speed"] * 2.2,
            reverse_thrust=120.0,
            turn_speed=self.BASE_TURN * self.profile["turn"],
            drag=1.1,
            max_speed=self.BASE_SPEED * self.profile["speed"],
            climb_speed=110.0,
        )
        self._avoid_buildings(buildings)
        return fired

    def _steer_toward(self, target_pos, target_altitude, dt):
        to_target = pygame.Vector2(target_pos) - self.pos
        if to_target.length_squared() > 1e-4:
            desired = math.degrees(math.atan2(to_target.y, to_target.x))
            # Shortest angular direction, normalized into -180..180.
            delta = (desired - self.angle + 180.0) % 360.0 - 180.0
            self.turn_input = clamp(delta / 45.0, -1.0, 1.0)
        self.thrust_input = 1.0
        alt_delta = target_altitude - self.altitude
        self.climb_input = clamp(alt_delta / 40.0, -1.0, 1.0)

    def _avoid_buildings(self, buildings):
        """Cheap reactive avoidance: if we're inside a block, climb over it."""
        for building in buildings:
            if building.blocks_at(self.pos.x, self.pos.y, self.altitude):
                self.altitude = min(constants.MAX_ALTITUDE, building.height + 18.0)
                break

    def _make_shot(self):
        direction = self.forward
        return {
            "pos": pygame.Vector2(self.pos),
            "altitude": self.altitude,
            "velocity": direction * 520.0,
            "damage": 1.0 * self.profile["damage"],
        }

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def draw(self, surface, camera):
        draw_shadow(surface, camera, self.pos, self.altitude, self.radius)
        sx, sy = camera.to_screen(self.pos.x, self.pos.y, self.altitude)
        center = pygame.Vector2(sx, sy)
        forward = self.forward
        right = pygame.Vector2(-forward.y, forward.x)
        size = self.radius

        nose = center + forward * size
        tail_l = center - forward * size * 0.7 + right * size * 0.7
        tail_r = center - forward * size * 0.7 - right * size * 0.7
        pygame.draw.polygon(surface, constants.ENEMY_DIM, [nose, tail_l, tail_r])
        pygame.draw.polygon(surface, constants.ENEMY_COLOR, [nose, tail_l, tail_r], width=2)

        if self.state != STATE_PATROL:
            pygame.draw.circle(surface, constants.DANGER, (int(sx), int(sy)), int(size * 1.9), width=1)
