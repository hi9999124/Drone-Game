import random

import pygame

from . import constants
from .entities.building import Building
from .entities.player_turret import PlayerTurret
from .entities.projectile import Explosion, Projectile
from .entities.pvo import PVO_UNITS_BY_KEY
from .entities.raider import RAIDER_PROFILES, RaiderDrone
from .world import RESULT_LOST, RESULT_PLAYING, RESULT_WON

SCORE_RAIDER = 60


class DefenseWorld:
    """Mission rules for Air Defense mode: the player mans a ground PVO unit
    protecting a cluster of civilian structures from waves of attacking
    BPLAs -- the inverse of World's "fly a drone and attack buildings".
    Shares entity classes (Building, Projectile, PVOUnitType stats -- see
    entities/pvo.py) so both sides of "PVO vs drones" are balanced against
    the same numbers, but keeps its own win/lose rules and update loop
    rather than mode-branching inside World, since the two are different
    enough that sharing one class would make both harder to follow.
    """

    mode = "defense"

    def __init__(self, unit_key, difficulty, seed=None):
        self.difficulty = difficulty
        self.profile = RAIDER_PROFILES.get(difficulty, RAIDER_PROFILES["Normal"])
        self.rng = random.Random(seed)

        self.buildings = []
        self.raiders = []
        self.projectiles = []
        self.explosions = []

        self.score = 0
        self.raiders_destroyed = 0
        self.structures_lost = 0
        self.result = RESULT_PLAYING
        self.message = ""
        self.message_timer = 0.0
        self.shake_request = 0.0

        self.wave = 0
        self.wave_total = self.profile["waves"]
        self.wave_timer = 3.0  # grace period before the first wave arrives
        self.wave_active = False

        self._generate_city()
        unit_type = PVO_UNITS_BY_KEY.get(unit_key, PVO_UNITS_BY_KEY["aagun"])
        # Ammo is a per-wave resource (replenished in _spawn_wave), not a
        # single mission-long pool -- SAM's real limiter is its cooldown
        # (same as the AI battery), flak's is the ammo count itself.
        self.player = PlayerTurret(0.0, 0.0, unit_type, ammo=30 if unit_type.key == "aagun" else 999)

    # ------------------------------------------------------------------ setup

    def _generate_city(self):
        half = constants.WORLD_SIZE * 0.5
        block = 420
        for gx in range(int(-half), int(half), block):
            for gy in range(int(-half), int(half), block):
                if self.rng.random() < 0.28:
                    continue
                width = self.rng.randint(150, 260)
                depth = self.rng.randint(130, 230)
                height = self.rng.choice([55, 80, 110, 140, 175, 200])
                x = gx + self.rng.randint(20, max(21, block - width - 20))
                y = gy + self.rng.randint(20, max(21, block - depth - 20))
                self.buildings.append(Building(x, y, width, depth, height))

        # Protect a cluster near the map's centre -- that's also where the
        # player's own turret sits, so the defended zone and the turret's
        # engagement range naturally overlap.
        candidates = [b for b in self.buildings if b.center.length() < 900]
        self.rng.shuffle(candidates)
        for building in candidates[:5]:
            building.is_protected = True
            building.max_hp = 260.0
            building.hp = 260.0

    # ----------------------------------------------------------------- helpers

    @property
    def protected(self):
        return [b for b in self.buildings if b.is_protected]

    @property
    def protected_remaining(self):
        return sum(1 for b in self.protected if not b.destroyed)

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

        self._update_waves(dt)
        self._update_player(dt, controls)
        self._update_raiders(dt)
        self._update_projectiles(dt)
        self._update_effects(dt)
        self._check_mission_state()

    def _update_waves(self, dt):
        if self.wave_active:
            if not self.raiders:
                self.wave_active = False
                self.wave_timer = self.profile["wave_gap"]
            return

        if self.wave >= self.wave_total:
            return
        self.wave_timer -= dt
        if self.wave_timer <= 0.0:
            self.wave += 1
            self.wave_active = True
            self._spawn_wave()
            self.notify(f"Wave {self.wave}/{self.wave_total} inbound")

    def _spawn_wave(self):
        self.player.ammo = self.player.max_ammo
        half = constants.WORLD_SIZE * 0.48
        for _ in range(self.profile["per_wave"]):
            edge = self.rng.choice(("n", "s", "e", "w"))
            if edge in ("n", "s"):
                x = self.rng.uniform(-half, half)
                y = -half if edge == "n" else half
            else:
                y = self.rng.uniform(-half, half)
                x = -half if edge == "w" else half
            self.raiders.append(RaiderDrone(x, y, self.profile))

    def _update_player(self, dt, controls):
        player = self.player
        if player is None or not player.alive_and_well:
            return
        player.set_input(controls.get("left", False), controls.get("right", False), controls.get("fire", False))
        player.update(dt)
        shot = player.try_fire()
        if shot:
            self.projectiles.append(
                Projectile(
                    "missile" if shot["homing"] else "rocket",
                    shot["pos"],
                    shot["altitude"],
                    shot["velocity"],
                    shot["blast_radius"],
                    shot["damage"],
                    friendly=True,
                    target=self._nearest_raider(shot["pos"]) if shot["homing"] else None,
                    turn_rate=shot["turn_rate"],
                )
            )

    def _nearest_raider(self, pos):
        alive = [r for r in self.raiders if r.alive]
        if not alive:
            return None
        return min(alive, key=lambda r: (r.pos - pos).length_squared())

    def _update_raiders(self, dt):
        for raider in self.raiders:
            if not raider.alive:
                continue
            hit = raider.update(dt, self.protected)
            if hit:
                self.detonate(hit["pos"], hit["altitude"], 70.0, hit["damage"], friendly=False)
        self.raiders = [r for r in self.raiders if r.alive]

    def _update_projectiles(self, dt):
        for projectile in list(self.projectiles):
            blast = projectile.update(dt, self.buildings, hit_targets=self.raiders)
            if blast:
                self.detonate(
                    blast["pos"], blast["altitude"], blast["radius"], blast["damage"], friendly=blast["friendly"]
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
            for raider in self.raiders:
                if not raider.alive:
                    continue
                dist = (raider.pos - pos).length()
                if dist <= radius and raider.take_damage(damage):
                    self.raiders_destroyed += 1
                    self.score += SCORE_RAIDER
        else:
            for building in self.protected:
                if building.destroyed:
                    continue
                closest_x = max(building.rect.left, min(pos.x, building.rect.right))
                closest_y = max(building.rect.top, min(pos.y, building.rect.bottom))
                dist = pygame.Vector2(closest_x - pos.x, closest_y - pos.y).length()
                if dist <= radius:
                    falloff = 1.0 - (dist / radius) * 0.6
                    if building.take_damage(damage * falloff):
                        self.structures_lost += 1
                        self.notify("A protected structure was destroyed")

            player = self.player
            if player is not None and player.alive_and_well:
                dist = (player.pos - pos).length()
                if dist <= radius and player.take_damage(damage * 0.3):
                    self.notify("Air defense unit destroyed")

    def _check_mission_state(self):
        if self.protected_remaining == 0:
            self.result = RESULT_LOST
            self.notify("All protected structures lost")
            return
        if self.player is not None and not self.player.alive_and_well:
            self.result = RESULT_LOST
            return
        if self.wave >= self.wave_total and not self.raiders and not self.wave_active:
            self.result = RESULT_WON
            self.score += self.protected_remaining * 150

    # ------------------------------------------------------------------ render

    def draw(self, surface, camera):
        self._draw_ground(surface, camera)

        drawables = []
        for building in self.buildings:
            if camera.is_visible(building.rect.centerx, building.rect.centery, 400):
                drawables.append((building.rect.bottom, building))
        for raider in self.raiders:
            if camera.is_visible(raider.pos.x, raider.pos.y):
                drawables.append((raider.pos.y, raider))
        for projectile in self.projectiles:
            drawables.append((projectile.pos.y, projectile))
        if self.player is not None and self.player.alive:
            drawables.append((self.player.pos.y, self.player))

        drawables.sort(key=lambda item: item[0])
        for _, entity in drawables:
            entity.draw(surface, camera)

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

        tl = camera.to_screen(-half, -half, 0)
        br = camera.to_screen(half, half, 0)
        pygame.draw.rect(
            surface, constants.ACCENT_DIM, (tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]), width=2
        )
