import random

import pygame

from . import constants
from .entities.building import Building
from .entities.player import PlayerDrone
from .entities.player_turret import PlayerTurret
from .entities.projectile import Explosion, Projectile
from .world import RESULT_LOST, RESULT_PLAYING, RESULT_WON

SCORE_TARGET = 250


class VersusWorld:
    """Stage 3 of the teams roadmap: a human Drone player against a human
    PVO player, sharing one authoritative simulation over the network
    (see src/net.py). The host's instance is the real simulation --
    physics, collisions, win/lose rules, everything World/DefenseWorld
    already do for their single-player equivalents. The client's instance
    only ever displays state (see apply_snapshot): it generates the exact
    same static city from a shared seed so nothing bulky has to be sent
    over the wire every frame, but never runs its own physics on the
    drone/turret/projectiles, which is what keeps the two sides from ever
    disagreeing about the outcome of a hit.

    Win conditions, deliberately just two and mutually exclusive (no draw
    state to handle): the Drone wins by destroying every target OR the PVO
    turret; the PVO side wins by exhausting the Drone's airframes.
    """

    mode = "versus"

    def __init__(self, drone_type, pvo_unit_type, difficulty, seed, is_host, local_role):
        self.is_host = is_host
        self.local_role = local_role  # "drone" or "pvo" -- which side THIS instance's human plays
        self.difficulty = difficulty
        self.seed = seed
        self.rng = random.Random(seed)

        self.buildings = []
        self.projectiles = []
        self.explosions = []

        self.score = 0  # the Drone side's score (target hits)
        self.pvo_score = 0  # the PVO side's score (airframes shot down) -- tracked separately since the two sides earn coins/XP independently
        self.result = RESULT_PLAYING
        self.message = ""
        self.message_timer = 0.0
        self.shake_request = 0.0

        self.drone_type = drone_type
        self.drone_units_left = drone_type.units
        self.respawn_timer = 0.0

        self._generate_city()
        spawn_x, spawn_y = self._find_clear_spawn()
        self.drone = PlayerDrone(drone_type, spawn_x, spawn_y)
        self.turret = PlayerTurret(0.0, 0.0, pvo_unit_type, ammo=999)

        self.player = self.drone if local_role == "drone" else self.turret

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

        candidates = [b for b in self.buildings if b.center.length() > 500]
        self.rng.shuffle(candidates)
        for building in candidates[:5]:
            building.is_target = True
            building.max_hp = 260.0
            building.hp = 260.0

    def _find_clear_spawn(self):
        for _ in range(60):
            x = self.rng.uniform(-constants.WORLD_SIZE * 0.45, constants.WORLD_SIZE * 0.45)
            y = constants.WORLD_SIZE * 0.46
            if not any(b.contains_point(x, y) for b in self.buildings):
                return x, y
        return 0.0, constants.WORLD_SIZE * 0.46

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

    # -------------------------------------------------------- host simulation

    def host_update(self, dt, drone_controls, pvo_controls):
        """Only ever called on the hosting machine. drone_controls/
        pvo_controls are each the same kind of dict _gather_controls()
        already produces locally, just one of them arrived over the network
        instead of from this machine's own keyboard/touch input."""
        self.shake_request = 0.0
        if self.message_timer > 0.0:
            self.message_timer -= dt

        if self.result != RESULT_PLAYING:
            self._update_effects(dt)
            return

        self._update_drone(dt, drone_controls)
        self._update_turret(dt, pvo_controls)
        self._update_projectiles(dt)
        self._update_effects(dt)
        self._check_mission_state(dt)

    def _update_drone(self, dt, controls):
        drone = self.drone
        if drone is None or not drone.alive_and_well:
            return
        drone.set_input(
            controls.get("thrust", False),
            controls.get("reverse", False),
            controls.get("left", False),
            controls.get("right", False),
            controls.get("ascend", False),
            controls.get("descend", False),
        )
        drone.update(dt)

        if controls.get("fire"):
            self._fire_drone_ability()

        self._resolve_drone_collisions()

    def _fire_drone_ability(self):
        drone = self.drone
        action = drone.use_ability()
        if action is None:
            return
        if action["kind"] == "bomb":
            self.projectiles.append(
                Projectile(
                    "bomb", drone.pos, drone.altitude, drone.vel,
                    drone.type.blast_radius, drone.type.blast_damage, friendly=True,
                )
            )
        elif action["kind"] == "rocket":
            self.projectiles.append(
                Projectile(
                    "rocket", drone.pos, drone.altitude, drone.forward * 780.0,
                    drone.type.blast_radius, drone.type.blast_damage, friendly=True,
                )
            )

    def _resolve_drone_collisions(self):
        drone = self.drone
        is_kamikaze = drone.type.attack == "ram"

        for building in self.buildings:
            if building.destroyed:
                continue
            if is_kamikaze and building.is_target and building.contains_point(drone.pos.x, drone.pos.y):
                self.detonate(drone.pos, drone.altitude, drone.type.blast_radius, drone.type.blast_damage, friendly=True)
                self._consume_drone_unit("Target struck")
                return
            if building.blocks_at(drone.pos.x, drone.pos.y, drone.altitude):
                self._crash_drone(is_kamikaze)
                return

        if self.turret.alive_and_well:
            dist = (drone.pos - self.turret.pos).length()
            if dist < drone.type.size + self.turret.type.size and abs(drone.altitude) < 40.0:
                self.detonate(drone.pos, drone.altitude, drone.type.blast_radius, drone.type.blast_damage, friendly=True)
                if is_kamikaze:
                    self._consume_drone_unit("Rammed the PVO unit")

    def _crash_drone(self, is_kamikaze):
        drone = self.drone
        self.detonate(drone.pos, drone.altitude, 60.0, 40.0, friendly=True)
        if is_kamikaze:
            self._consume_drone_unit("Hit a building")
            return
        destroyed = drone.take_damage(2.0)
        drone.pos -= drone.vel.normalize() * 45 if drone.vel.length_squared() > 1 else pygame.Vector2(0, 45)
        drone.vel *= 0.2
        drone.invulnerable = 0.8
        self.shake_request = max(self.shake_request, 7.0)
        if destroyed:
            self._consume_drone_unit("Hit a building")
        else:
            self.notify("Hit a building")

    def _consume_drone_unit(self, reason):
        self.drone_units_left -= 1
        self.shake_request = max(self.shake_request, 12.0)
        self.drone.alive = False
        if self.drone_units_left > 0:
            self.respawn_timer = 1.4
            self.notify(f"{reason} - {self.drone_units_left} airframe(s) left")
        else:
            self.notify(reason)

    def _update_turret(self, dt, controls):
        turret = self.turret
        if turret is None or not turret.alive_and_well:
            return
        turret.set_input(controls.get("left", False), controls.get("right", False), controls.get("fire", False))
        turret.update(dt)
        shot = turret.try_fire()
        if shot:
            self.projectiles.append(
                Projectile(
                    "missile" if shot["homing"] else "rocket",
                    shot["pos"], shot["altitude"], shot["velocity"],
                    shot["blast_radius"], shot["damage"], friendly=False,
                    target=self.drone if shot["homing"] else None,
                    turn_rate=shot["turn_rate"],
                )
            )

    def _update_projectiles(self, dt):
        for projectile in list(self.projectiles):
            hit_targets = [self.drone] if not projectile.friendly else [self.turret]
            blast = projectile.update(dt, self.buildings, hit_targets=hit_targets)
            if blast:
                self.detonate(blast["pos"], blast["altitude"], blast["radius"], blast["damage"], friendly=blast["friendly"])
        self.projectiles = [p for p in self.projectiles if p.alive]

    def _update_effects(self, dt):
        for explosion in self.explosions:
            explosion.update(dt)
        self.explosions = [e for e in self.explosions if e.alive]

    def detonate(self, pos, altitude, radius, damage, friendly=True):
        self.explosions.append(Explosion(pos, altitude, radius))
        self.shake_request = max(self.shake_request, min(16.0, radius * 0.07))

        if friendly:
            # The Drone's ordnance -- can hit targets (win condition) or the
            # PVO turret directly (the other win condition).
            for building in self.buildings:
                if not building.is_target or building.destroyed:
                    continue
                closest_x = max(building.rect.left, min(pos.x, building.rect.right))
                closest_y = max(building.rect.top, min(pos.y, building.rect.bottom))
                dist = pygame.Vector2(closest_x - pos.x, closest_y - pos.y).length()
                if dist <= radius:
                    falloff = 1.0 - (dist / radius) * 0.6
                    if building.take_damage(damage * falloff):
                        self.score += SCORE_TARGET
                        self.notify("Target destroyed")
            turret = self.turret
            if turret is not None and turret.alive_and_well:
                dist = (turret.pos - pos).length()
                if dist <= radius and turret.take_damage(damage * 0.6):
                    self.notify("PVO unit destroyed")
        else:
            # The PVO turret's fire -- only ever threatens the Drone.
            drone = self.drone
            if drone is not None and drone.alive_and_well:
                dist = pygame.Vector2(drone.pos.x - pos.x, drone.pos.y - pos.y).length()
                if dist <= radius and abs(drone.altitude - altitude) <= radius:
                    if drone.take_damage(damage):
                        self.pvo_score += 150
                        self._consume_drone_unit("Shot down")

    def _check_mission_state(self, dt):
        if self.targets_remaining == 0 or not self.turret.alive_and_well:
            self.result = RESULT_WON  # "won" from the Drone's perspective; each client's UI reframes this per local_role
            self.score += self.drone_units_left * 100
            return
        if self.drone_units_left <= 0 and not self.drone.alive:
            self.result = RESULT_LOST
            return
        if self.drone is not None and not self.drone.alive:
            if self.drone_units_left > 0:
                self.respawn_timer -= dt
                if self.respawn_timer <= 0.0:
                    x, y = self._find_clear_spawn()
                    self.drone = PlayerDrone(self.drone_type, x, y)
                    if self.local_role == "drone":
                        self.player = self.drone

    # ------------------------------------------------------ client application

    def apply_snapshot(self, snap):
        """Client-side only: overwrite every piece of dynamic state from the
        host's latest broadcast. Never runs physics locally -- see the
        class docstring for why that's the point, not a limitation."""
        d = snap["drone"]
        if d is None:
            self.drone.alive = False
        else:
            self.drone.pos.x, self.drone.pos.y = d["pos"]
            self.drone.angle = d["angle"]
            self.drone.altitude = d["altitude"]
            self.drone.hp = d["hp"]
            self.drone.alive = d["alive"]
            self.drone.boost_time = d["boost_time"]
            self.drone.invulnerable = d["invulnerable"]

        t = snap["turret"]
        self.turret.pos.x, self.turret.pos.y = t["pos"]
        self.turret.angle = t["angle"]
        self.turret.hp = t["hp"]
        self.turret.alive = t["alive"]
        self.turret.ammo = t["ammo"]
        self.turret.cooldown = t["cooldown"]

        self.projectiles = [
            Projectile(p["kind"], p["pos"], p["altitude"], p["vel"], 0.0, 0.0, friendly=p["friendly"])
            for p in snap["projectiles"]
        ]

        for index, bstate in snap["buildings"]:
            building = self.buildings[index]
            building.hp = bstate["hp"]
            building.destroyed = bstate["destroyed"]

        self.drone_units_left = snap["drone_units_left"]
        self.score = snap["score"]
        self.pvo_score = snap["pvo_score"]
        self.result = snap["result"]
        if snap.get("message") and snap["message"] != self.message:
            self.notify(snap["message"])

        # apply_snapshot is called after PlayerDrone's independent identity
        # (respawn creates a brand new instance host-side) already collapsed
        # into plain position/hp fields above, so self.player just needs to
        # keep pointing at whichever object this client's human controls.
        self.player = self.drone if self.local_role == "drone" else self.turret

    def build_snapshot(self):
        """Host-side only: the payload sent to the client every network
        tick. Static geometry (building rects/heights) is deliberately
        excluded -- both sides generated the identical city from the same
        seed already, so only what actually changes needs to cross the wire."""
        return {
            "drone": None
            if self.drone is None
            else {
                "pos": [self.drone.pos.x, self.drone.pos.y],
                "angle": self.drone.angle,
                "altitude": self.drone.altitude,
                "hp": self.drone.hp,
                "alive": self.drone.alive,
                "boost_time": self.drone.boost_time,
                "invulnerable": self.drone.invulnerable,
            },
            "turret": {
                "pos": [self.turret.pos.x, self.turret.pos.y],
                "angle": self.turret.angle,
                "hp": self.turret.hp,
                "alive": self.turret.alive,
                "ammo": self.turret.ammo,
                "cooldown": self.turret.cooldown,
            },
            "projectiles": [
                {
                    "kind": p.kind,
                    "pos": [p.pos.x, p.pos.y],
                    "altitude": p.altitude,
                    "vel": [p.vel.x, p.vel.y],
                    "friendly": p.friendly,
                }
                for p in self.projectiles
            ],
            "buildings": [
                (i, {"hp": b.hp, "destroyed": b.destroyed}) for i, b in enumerate(self.buildings) if b.is_target
            ],
            "drone_units_left": self.drone_units_left,
            "score": self.score,
            "pvo_score": self.pvo_score,
            "result": self.result,
            "message": self.message if self.message_timer > 0.0 else "",
        }

    # ------------------------------------------------------------------ render

    def draw(self, surface, camera):
        self._draw_ground(surface, camera)

        drawables = []
        for building in self.buildings:
            if camera.is_visible(building.rect.centerx, building.rect.centery, 400):
                drawables.append((building.rect.bottom, building))
        drawables.append((self.turret.pos.y, self.turret))
        for projectile in self.projectiles:
            drawables.append((projectile.pos.y, projectile))
        if self.drone is not None and self.drone.alive:
            drawables.append((self.drone.pos.y, self.drone))

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
