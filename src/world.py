import random

import pygame

from . import constants
from .entities.building import Building
from .entities.enemy import DIFFICULTY_PROFILES, EnemyDrone
from .entities.player import PlayerDrone
from .entities.projectile import Explosion, Projectile

SCORE_TARGET = 250
SCORE_ENEMY = 75

RESULT_PLAYING = "playing"
RESULT_WON = "won"
RESULT_LOST = "lost"


class World:
    """Owns the city, everything flying in it, and the win/lose rules."""

    def __init__(self, drone_type, difficulty, seed=None):
        self.drone_type = drone_type
        self.difficulty = difficulty
        self.profile = DIFFICULTY_PROFILES.get(difficulty, DIFFICULTY_PROFILES["Normal"])
        self.rng = random.Random(seed)

        self.buildings = []
        self.enemies = []
        self.projectiles = []
        self.explosions = []

        self.score = 0
        self.targets_destroyed = 0
        self.enemies_destroyed = 0
        self.units_left = drone_type.units
        self.result = RESULT_PLAYING
        self.respawn_timer = 0.0
        self.message = ""
        self.message_timer = 0.0
        self.shake_request = 0.0

        self._generate_city()
        self._spawn_enemies()
        self.player = self._spawn_player()

    # ------------------------------------------------------------------ setup

    def _generate_city(self):
        """Lay out apartment blocks on a loose grid with gaps for streets."""
        half = constants.WORLD_SIZE * 0.5
        block = 420
        for gx in range(int(-half), int(half), block):
            for gy in range(int(-half), int(half), block):
                if self.rng.random() < 0.28:
                    continue  # empty lot / park
                width = self.rng.randint(150, 260)
                depth = self.rng.randint(130, 230)
                height = self.rng.choice([55, 80, 110, 140, 175, 200])
                x = gx + self.rng.randint(20, max(21, block - width - 20))
                y = gy + self.rng.randint(20, max(21, block - depth - 20))
                self.buildings.append(Building(x, y, width, depth, height))

        # Promote a handful of blocks to mission targets, biased away from spawn.
        candidates = [b for b in self.buildings if b.center.length() > 500]
        self.rng.shuffle(candidates)
        for building in candidates[:5]:
            building.is_target = True
            building.max_hp = 260.0
            building.hp = 260.0

    def _spawn_enemies(self):
        half = constants.WORLD_SIZE * 0.42
        for _ in range(self.profile["count"]):
            x = self.rng.uniform(-half, half)
            y = self.rng.uniform(-half, half)
            self.enemies.append(EnemyDrone(x, y, self.profile))

    def _find_clear_spawn(self):
        """Spawn on the map edge, never inside a building."""
        for _ in range(60):
            x = self.rng.uniform(-constants.WORLD_SIZE * 0.45, constants.WORLD_SIZE * 0.45)
            y = constants.WORLD_SIZE * 0.46
            if not any(b.contains_point(x, y) for b in self.buildings):
                return x, y
        return 0.0, constants.WORLD_SIZE * 0.46

    def _spawn_player(self):
        x, y = self._find_clear_spawn()
        return PlayerDrone(self.drone_type, x, y)

    # ----------------------------------------------------------------- helpers

    @property
    def targets(self):
        return [b for b in self.buildings if b.is_target]

    @property
    def targets_remaining(self):
        return sum(1 for b in self.targets if not b.destroyed)

    def notify(self, text, duration=2.2):
        self.message = text
        self.message_timer = duration

    # ------------------------------------------------------------------ update

    def update(self, dt, controls):
        self.shake_request = 0.0
        if self.message_timer > 0.0:
            self.message_timer -= dt

        if self.result != RESULT_PLAYING:
            self._update_effects(dt)
            return

        self._update_player(dt, controls)
        self._update_enemies(dt)
        self._update_projectiles(dt)
        self._update_effects(dt)
        self._check_mission_state(dt)

    def _update_player(self, dt, controls):
        player = self.player
        if player is None:
            return
        if not player.alive_and_well:
            return

        player.set_input(
            controls.get("thrust", False),
            controls.get("reverse", False),
            controls.get("left", False),
            controls.get("right", False),
            controls.get("ascend", False),
            controls.get("descend", False),
        )
        player.update(dt)

        if controls.get("fire"):
            self._fire_ability()

        self._resolve_player_collisions()

    def _fire_ability(self):
        player = self.player
        action = player.use_ability()
        if action is None:
            return
        if action["kind"] == "bomb":
            self.projectiles.append(
                Projectile(
                    "bomb",
                    player.pos,
                    player.altitude,
                    player.vel,  # bombs keep the drone's momentum
                    player.type.blast_radius,
                    player.type.blast_damage,
                )
            )
        elif action["kind"] == "rocket":
            self.projectiles.append(
                Projectile(
                    "rocket",
                    player.pos,
                    player.altitude,
                    player.forward * 780.0,
                    player.type.blast_radius,
                    player.type.blast_damage,
                )
            )

    def _resolve_player_collisions(self):
        player = self.player
        is_kamikaze = player.type.attack == "ram"

        for building in self.buildings:
            if building.destroyed:
                continue

            # A kamikaze drone rams a target the moment it crosses the
            # footprint, regardless of altitude. Gating this on
            # blocks_at()'s altitude<height check meant a drone flying at
            # its (fixed, no-gravity) spawn altitude of 110 could never
            # touch off roughly half the city's buildings (heights
            # 55/80/110 in the generator) no matter how precisely you flew
            # into them -- functionally "can't hit any building" for
            # anyone who never discovers the climb/descend keys.
            if is_kamikaze and building.is_target and building.contains_point(player.pos.x, player.pos.y):
                self._ram_strike(building)
                return

            if building.blocks_at(player.pos.x, player.pos.y, player.altitude):
                # Non-ram airframes (or ramming a non-target) just crash into it.
                self._crash(player, "Hit a building")
                return

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            if player.distance_to(enemy) < player.type.size + enemy.radius:
                enemy.take_damage(99)
                self.enemies_destroyed += 1
                self.score += SCORE_ENEMY
                self.detonate(enemy.pos, enemy.altitude, 70.0, 60.0, friendly=True)
                if player.type.attack == "ram":
                    self._consume_unit("Rammed an interceptor")
                else:
                    player.take_damage(1.0)
                return

    def _ram_strike(self, building):
        player = self.player
        self.detonate(
            player.pos,
            player.altitude,
            player.type.blast_radius,
            player.type.blast_damage,
            friendly=True,
        )
        self._consume_unit("Target struck")

    def _crash(self, player, reason):
        self.detonate(player.pos, player.altitude, 60.0, 40.0, friendly=True)
        if player.type.attack == "ram":
            self._consume_unit(reason)
        else:
            destroyed = player.take_damage(2.0)
            # Push the drone back out of the wall so it doesn't re-collide
            # every frame while the player recovers.
            player.pos -= player.vel.normalize() * 45 if player.vel.length_squared() > 1 else pygame.Vector2(0, 45)
            player.vel *= 0.2
            player.invulnerable = 0.8
            self.shake_request = max(self.shake_request, 7.0)
            if destroyed:
                self._consume_unit(reason)
            else:
                self.notify(reason)

    def _consume_unit(self, reason):
        self.units_left -= 1
        self.shake_request = max(self.shake_request, 12.0)
        self.player.alive = False
        if self.units_left > 0:
            self.respawn_timer = 1.4
            self.notify(f"{reason} - {self.units_left} airframe(s) left")
        else:
            self.notify(reason)

    def _update_enemies(self, dt):
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            shot = enemy.update(dt, self.player, self.buildings)
            if shot:
                self.projectiles.append(
                    Projectile(
                        "rocket",
                        shot["pos"],
                        shot["altitude"],
                        shot["velocity"],
                        60.0,
                        shot["damage"],
                        friendly=False,
                    )
                )
        self.enemies = [e for e in self.enemies if e.alive]

    def _update_projectiles(self, dt):
        for projectile in list(self.projectiles):
            blast = projectile.update(dt, self.buildings)
            if blast:
                self.detonate(
                    blast["pos"],
                    blast["altitude"],
                    blast["radius"],
                    blast["damage"],
                    friendly=blast["friendly"],
                )
        self.projectiles = [p for p in self.projectiles if p.alive]

    def _update_effects(self, dt):
        for explosion in self.explosions:
            explosion.update(dt)
        self.explosions = [e for e in self.explosions if e.alive]

    def detonate(self, pos, altitude, radius, damage, friendly=True):
        self.explosions.append(Explosion(pos, altitude, radius))
        self.shake_request = max(self.shake_request, min(16.0, radius * 0.07))

        if friendly:
            for building in self.buildings:
                if not building.is_target or building.destroyed:
                    continue
                # Distance to the footprint, not just its centre, so clipping a
                # corner of a long block still counts.
                closest_x = max(building.rect.left, min(pos.x, building.rect.right))
                closest_y = max(building.rect.top, min(pos.y, building.rect.bottom))
                dist = pygame.Vector2(closest_x - pos.x, closest_y - pos.y).length()
                if dist <= radius:
                    falloff = 1.0 - (dist / radius) * 0.6
                    if building.take_damage(damage * falloff):
                        self.targets_destroyed += 1
                        self.score += SCORE_TARGET
                        self.notify("Target destroyed")

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dist = pygame.Vector2(enemy.pos.x - pos.x, enemy.pos.y - pos.y).length()
            if dist <= radius and abs(enemy.altitude - altitude) <= radius:
                if enemy.take_damage(damage * 0.05):
                    self.enemies_destroyed += 1
                    self.score += SCORE_ENEMY

        player = self.player
        if player is not None and player.alive_and_well:
            dist = pygame.Vector2(player.pos.x - pos.x, player.pos.y - pos.y).length()
            if not friendly and dist <= radius and abs(player.altitude - altitude) <= radius:
                if player.take_damage(damage):
                    self._consume_unit("Shot down")

    def _check_mission_state(self, dt):
        if self.targets_remaining == 0:
            self.result = RESULT_WON
            # Surviving airframes are worth something -- rewards a clean run.
            self.score += self.units_left * 100
            return

        if self.player is not None and not self.player.alive:
            if self.units_left > 0:
                self.respawn_timer -= dt
                if self.respawn_timer <= 0.0:
                    self.player = self._spawn_player()
            else:
                self.result = RESULT_LOST

    # ------------------------------------------------------------------ render

    def draw(self, surface, camera):
        self._draw_ground(surface, camera)

        # Painter's algorithm: sort everything by its world Y so nearer objects
        # (larger Y, lower on screen) are drawn last and overlap what's behind.
        drawables = []
        for building in self.buildings:
            if camera.is_visible(building.rect.centerx, building.rect.centery, 400):
                drawables.append((building.rect.bottom, building))
        for enemy in self.enemies:
            if camera.is_visible(enemy.pos.x, enemy.pos.y):
                drawables.append((enemy.pos.y, enemy))
        for projectile in self.projectiles:
            drawables.append((projectile.pos.y, projectile))
        if self.player is not None and self.player.alive:
            drawables.append((self.player.pos.y, self.player))

        drawables.sort(key=lambda item: item[0])
        for _, entity in drawables:
            entity.draw(surface, camera)

        # Explosions draw on top of everything -- they're the loudest event
        # on screen and shouldn't be hidden behind a roof.
        for explosion in self.explosions:
            explosion.draw(surface, camera)

    def _draw_ground(self, surface, camera):
        surface.fill(constants.GROUND_COLOR)
        spacing = 140
        half = constants.WORLD_SIZE * 0.5
        start_x = int((camera.pos.x - constants.WIDTH * 0.5) // spacing * spacing)
        start_y = int((camera.pos.y - constants.HEIGHT * 0.5) // spacing * spacing)

        for i in range(int(constants.WIDTH / spacing) + 3):
            wx = start_x + i * spacing
            sx, _ = camera.to_screen(wx, 0, 0)
            pygame.draw.line(surface, constants.GRID_COLOR, (sx, 0), (sx, constants.HEIGHT))
        for i in range(int(constants.HEIGHT / spacing) + 3):
            wy = start_y + i * spacing
            _, sy = camera.to_screen(0, wy, 0)
            pygame.draw.line(surface, constants.GRID_COLOR, (0, sy), (constants.WIDTH, sy))

        # World boundary, so the edge of the map is legible in-flight.
        tl = camera.to_screen(-half, -half, 0)
        br = camera.to_screen(half, half, 0)
        pygame.draw.rect(
            surface, constants.ACCENT_DIM, (tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]), width=2
        )
