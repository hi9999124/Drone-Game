import random

import pygame

from . import constants
from .entities.building import Building
from .entities.civilian import Civilian
from .world import RESULT_LOST, RESULT_PLAYING, RESULT_WON

SURVIVAL_PROFILES = {
    "Easy": dict(duration=75.0, strike_interval=4.0, warn_time=2.4, blast_radius=110.0, damage=1.0),
    "Normal": dict(duration=90.0, strike_interval=3.0, warn_time=1.9, blast_radius=120.0, damage=1.0),
    "Hard": dict(duration=105.0, strike_interval=2.2, warn_time=1.5, blast_radius=130.0, damage=1.0),
    "Insane": dict(duration=120.0, strike_interval=1.6, warn_time=1.1, blast_radius=140.0, damage=1.0),
}


class SurvivalWorld:
    """Mission rules for Civilian Survival mode: on foot, no weapon, reach
    shelter before a telegraphed strike lands. Deliberately a different
    verb from both other modes -- Drone Strike is flying and attacking,
    Air Defense is aiming and shooting, this is reading the map and
    reacting to a countdown. The threat is continuous rather than wave-
    based (see DefenseWorld) since a steady bombardment fits "surviving a
    strike" better than "surviving discrete raids".
    """

    mode = "survival"

    def __init__(self, difficulty, seed=None):
        self.difficulty = difficulty
        self.profile = SURVIVAL_PROFILES.get(difficulty, SURVIVAL_PROFILES["Normal"])
        self.rng = random.Random(seed)

        self.buildings = []
        self.strikes = []  # each: {"pos", "timer", "warn_time", "radius", "damage", "resolved"}
        self.explosions = []

        self.score = 0
        self.strikes_survived = 0
        self.result = RESULT_PLAYING
        self.message = ""
        self.message_timer = 0.0
        self.shake_request = 0.0

        self.elapsed = 0.0
        self.duration = self.profile["duration"]
        self._strike_timer = 2.0  # brief grace period before the first strike

        self._generate_city()
        self.player = Civilian(0.0, 0.0)

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

        # Shelters scattered through the play area the strikes actually
        # target (see _strike_zone_radius), not off in the empty outskirts.
        candidates = [b for b in self.buildings if b.center.length() < 900]
        self.rng.shuffle(candidates)
        for building in candidates[:6]:
            building.is_shelter = True

    def _strike_zone_radius(self):
        return constants.WORLD_SIZE * 0.32

    # ----------------------------------------------------------------- helpers

    def in_shelter(self, pos):
        return any(
            b.is_shelter and b.rect.collidepoint(pos.x, pos.y) for b in self.buildings
        )

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

        self.elapsed += dt
        self._update_player(dt, controls)
        self._update_strikes(dt)
        self._update_effects(dt)
        self._check_mission_state()

    def _update_player(self, dt, controls):
        player = self.player
        if player is None or not player.alive_and_well:
            return
        player.set_input(
            controls.get("thrust", False),
            controls.get("reverse", False),
            controls.get("left", False),
            controls.get("right", False),
        )
        player.update(dt)

    def _update_strikes(self, dt):
        self._strike_timer -= dt
        if self._strike_timer <= 0.0:
            self._strike_timer = self.profile["strike_interval"]
            self._spawn_strike()

        for strike in self.strikes:
            strike["timer"] -= dt
            if strike["timer"] <= 0.0:
                self._resolve_strike(strike)
        # The impact flash (_StrikeFlash, added in _resolve_strike) is what
        # actually lingers on screen -- a resolved strike itself has nothing
        # left to do once damage/scoring has been applied.
        self.strikes = [s for s in self.strikes if not s["resolved"]]

    def _spawn_strike(self):
        radius = self._strike_zone_radius()
        x = self.rng.uniform(-radius, radius)
        y = self.rng.uniform(-radius, radius)
        self.strikes.append(
            {
                "pos": pygame.Vector2(x, y),
                "timer": self.profile["warn_time"],
                "warn_time": self.profile["warn_time"],
                "radius": self.profile["blast_radius"],
                "damage": self.profile["damage"],
                "resolved": False,
            }
        )

    def _resolve_strike(self, strike):
        strike["resolved"] = True
        self.explosions.append(_StrikeFlash(strike["pos"], strike["radius"]))
        self.shake_request = max(self.shake_request, min(16.0, strike["radius"] * 0.06))

        player = self.player
        if player is None or not player.alive_and_well:
            return
        if self.in_shelter(player.pos):
            self.strikes_survived += 1
            self.score += 40
            return
        dist = (player.pos - strike["pos"]).length()
        if dist <= strike["radius"]:
            if player.take_damage(strike["damage"]):
                self.notify("Caught in the open")
            else:
                self.notify("Hit -- find shelter")
        else:
            self.strikes_survived += 1
            self.score += 40

    def _update_effects(self, dt):
        for explosion in self.explosions:
            explosion.update(dt)
        self.explosions = [e for e in self.explosions if e.alive]

    def _check_mission_state(self):
        if self.player is not None and not self.player.alive_and_well:
            self.result = RESULT_LOST
            return
        if self.elapsed >= self.duration:
            self.result = RESULT_WON
            self.score += int(self.player.hp) * 100

    # ------------------------------------------------------------------ render

    def draw(self, surface, camera):
        self._draw_ground(surface, camera)

        drawables = []
        for building in self.buildings:
            if camera.is_visible(building.rect.centerx, building.rect.centery, 400):
                drawables.append((building.rect.bottom, building))
        if self.player is not None and self.player.alive:
            drawables.append((self.player.pos.y, self.player))
        drawables.sort(key=lambda item: item[0])
        for _, entity in drawables:
            entity.draw(surface, camera)

        for strike in self.strikes:
            if not strike["resolved"]:
                self._draw_strike_warning(surface, camera, strike)
        for explosion in self.explosions:
            explosion.draw(surface, camera)

    def _draw_strike_warning(self, surface, camera, strike):
        sx, sy = camera.to_screen(strike["pos"].x, strike["pos"].y, 0.0)
        t = 1.0 - (strike["timer"] / strike["warn_time"])
        pulse = 0.7 + 0.3 * abs(((t * 6.0) % 2.0) - 1.0)
        radius = int(strike["radius"] * pulse)
        ring = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        alpha = int(90 + 90 * t)
        pygame.draw.circle(ring, (*constants.DANGER, alpha), (radius, radius), radius, width=3)
        surface.blit(ring, (sx - radius, sy - radius))

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


class _StrikeFlash:
    """Purely visual impact flash -- damage was already applied the instant
    the strike resolved, same as Explosion elsewhere in the game."""

    def __init__(self, pos, radius):
        self.pos = pygame.Vector2(pos)
        self.radius = radius
        self.age = 0.0
        self.duration = 0.4
        self.alive = True

    def update(self, dt):
        self.age += dt
        if self.age >= self.duration:
            self.alive = False

    def draw(self, surface, camera):
        t = self.age / self.duration
        current = self.radius * (0.5 + 0.5 * t)
        alpha = int(200 * (1.0 - t))
        sx, sy = camera.to_screen(self.pos.x, self.pos.y, 0.0)
        size = int(current * 2)
        if size <= 0:
            return
        blast = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(blast, (255, 120, 90, alpha), (int(current), int(current)), int(current))
        surface.blit(blast, (sx - current, sy - current))
