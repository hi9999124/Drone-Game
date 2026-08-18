import pygame

from . import constants
from .entities.building import Building
from .entities.prop import PROPS_BY_KEY, Prop
from .world import World

# What a levelled block is worth. Scaled by height on top of this, so
# flattening a 200 m tower pays better than a 55 m shed.
SCORE_BLOCK_BASE = 45
SCORE_BLOCK_PER_METRE = 0.55

# Free Flight hands the ammo back instead of ending the session: a rocket
# platform tops up one round at a time, and a kamikaze always gets another
# airframe. Running dry in a sandbox just means sitting there.
REARM_INTERVAL = 2.2
RESPAWN_DELAY = 1.1


class SandboxWorld(World):
    """Free Flight: the whole city is destructible and nothing shoots back.

    Deliberately the opposite shape from every other mode -- no targets to
    find, no waves, no timer, no fail state. What it does have is a city where
    every block has HP, streets full of fuel tanks that chain off each other,
    and weapons that reload themselves, so the only thing to do is fly and
    take things apart.

    It reuses World for physics, collision and blast resolution; the overrides
    below are exactly the mission rules that don't apply to a sandbox.
    """

    mode = "sandbox"

    # A fuel tank's blast can pop the next tank along, but a chain has to
    # terminate: three links deep is plenty for a depot going up and can't
    # recurse the frame into a stall.
    MAX_CHAIN_DEPTH = 3

    def __init__(self, drone_type, difficulty="Normal", seed=None):
        # Populated by _generate_city, which World.__init__ calls -- has to
        # exist before that runs.
        self.props = []
        self.blocks_destroyed = 0
        self.props_destroyed = 0
        self.airframes_lost = 0
        self._rearm_timer = REARM_INTERVAL
        super().__init__(drone_type, difficulty, seed)
        self.block_total = len(self.buildings)
        self.prop_total = len(self.props)

    # ------------------------------------------------------------------ setup

    def _generate_city(self):
        """Same loose grid as a strike mission, but every block has HP and the
        streets between them are stocked with things that explode."""
        half = constants.WORLD_SIZE * 0.5
        block = 420
        for gx in range(int(-half), int(half), block):
            for gy in range(int(-half), int(half), block):
                if self.rng.random() < 0.24:
                    self._scatter_lot_props(gx, gy, block)
                    continue  # empty lot / fuel yard
                width = self.rng.randint(150, 260)
                depth = self.rng.randint(130, 230)
                height = self.rng.choice([55, 80, 110, 140, 175, 200])
                x = gx + self.rng.randint(20, max(21, block - width - 20))
                y = gy + self.rng.randint(20, max(21, block - depth - 20))
                building = Building(x, y, width, depth, height)
                # Taller blocks are sturdier, so levelling a tower is a
                # commitment (several bomb runs) rather than one lucky pass.
                building.make_destructible(90.0 + height * 1.15)
                self.buildings.append(building)
                self._scatter_street_props(building)

    def _scatter_lot_props(self, gx, gy, block):
        """An empty lot becomes a fuel yard: the sandbox's best payoff, since
        the tanks chain into each other."""
        if self.rng.random() < 0.45:
            return  # genuinely empty, so the city still breathes
        fuel = PROPS_BY_KEY["fuel"]
        tanker = PROPS_BY_KEY["tanker"]
        count = self.rng.randint(2, 5)
        cx = gx + block * 0.5
        cy = gy + block * 0.5
        for _ in range(count):
            offset = pygame.Vector2(self.rng.uniform(30, 150), 0).rotate(self.rng.uniform(0, 360))
            prop_type = fuel if self.rng.random() < 0.65 else tanker
            self.props.append(Prop(cx + offset.x, cy + offset.y, prop_type))

    def _scatter_street_props(self, building):
        """Cars parked along a block, and the odd comms mast on its roofline."""
        car = PROPS_BY_KEY["car"]
        for _ in range(self.rng.randint(0, 3)):
            side = self.rng.choice(["left", "right", "top", "bottom"])
            if side == "left":
                x, y = building.rect.left - self.rng.uniform(18, 46), self.rng.uniform(*sorted((building.rect.top, building.rect.bottom)))
            elif side == "right":
                x, y = building.rect.right + self.rng.uniform(18, 46), self.rng.uniform(*sorted((building.rect.top, building.rect.bottom)))
            elif side == "top":
                x, y = self.rng.uniform(*sorted((building.rect.left, building.rect.right))), building.rect.top - self.rng.uniform(18, 46)
            else:
                x, y = self.rng.uniform(*sorted((building.rect.left, building.rect.right))), building.rect.bottom + self.rng.uniform(18, 46)
            self.props.append(Prop(x, y, car))

        if self.rng.random() < 0.12:
            tower = PROPS_BY_KEY["tower"]
            self.props.append(
                Prop(building.rect.right + self.rng.uniform(50, 90), building.rect.centery, tower)
            )

    def _spawn_enemies(self):
        pass  # free flight: nothing hostile in the air

    def _spawn_pvo_defenses(self):
        pass  # ...and nothing shooting from the ground either

    # ----------------------------------------------------------------- helpers

    @property
    def blocks_remaining(self):
        return sum(1 for b in self.buildings if not b.destroyed)

    @property
    def destruction_fraction(self):
        if not self.block_total:
            return 0.0
        return self.blocks_destroyed / self.block_total

    # ------------------------------------------------------------------ update

    def _update_player(self, dt, controls):
        super()._update_player(dt, controls)
        self._rearm(dt)

    def _rearm(self, dt):
        """Trickle ordnance back so a session never dead-ends on an empty rack."""
        player = self.player
        if player is None or not player.alive_and_well:
            return
        if player.type.attack == "ram" or player.ammo >= player.type.ammo:
            self._rearm_timer = REARM_INTERVAL
            return
        self._rearm_timer -= dt
        if self._rearm_timer <= 0.0:
            self._rearm_timer = REARM_INTERVAL
            player.ammo = min(player.type.ammo, player.ammo + 1)

    def _update_effects(self, dt):
        super()._update_effects(dt)
        for prop in self.props:
            prop.update(dt)

    def _resolve_player_collisions(self):
        """Fly into anything and it goes up -- there are no "wrong" things to
        hit here, which is the whole point of the mode. World's version only
        lets a kamikaze detonate against a *marked target*; every block is a
        target now, and the street props are too."""
        player = self.player
        is_kamikaze = player.type.attack == "ram"

        for building in self.buildings:
            if building.blocks_at(player.pos.x, player.pos.y, player.altitude):
                if is_kamikaze:
                    self.detonate(
                        player.pos,
                        player.altitude,
                        player.type.blast_radius,
                        player.type.blast_damage,
                        friendly=True,
                    )
                    self._consume_unit("Impact")
                else:
                    self._crash(player, "Hit a building")
                return

        for prop in self.props:
            if prop.destroyed:
                continue
            if player.altitude > prop.type.height:
                continue
            if not prop.contains_point(player.pos.x, player.pos.y):
                continue
            if is_kamikaze:
                self.detonate(
                    player.pos, player.altitude, player.type.blast_radius, player.type.blast_damage
                )
                self._consume_unit("Impact")
            else:
                # Clipping a car shouldn't cost the airframe outright, but it
                # takes the car with it and rattles the drone.
                self.detonate(prop.pos, prop.type.height * 0.5, prop.type.blast_radius * 0.6, prop.type.hp * 2.0)
                self._crash(player, f"Clipped a {prop.type.name.lower()}")
            return

    def _consume_unit(self, reason):
        """Airframes are free here: losing one is a respawn, not a loss."""
        self.airframes_lost += 1
        self.shake_request = max(self.shake_request, 12.0)
        self.player.alive = False
        self.respawn_timer = RESPAWN_DELAY
        self.notify(reason)

    def _check_mission_state(self, dt):
        """No win, no loss -- just keep putting the player back in the air."""
        player = self.player
        if player is not None and not player.alive:
            self.respawn_timer -= dt
            if self.respawn_timer <= 0.0:
                self.player = self._spawn_player()

    # ---------------------------------------------------------------- damage

    def detonate(self, pos, altitude, radius, damage, friendly=True, depth=0):
        super().detonate(pos, altitude, radius, damage, friendly)
        self._damage_props(pos, altitude, radius, damage, depth)

    def _damage_props(self, pos, altitude, radius, damage, depth):
        chain = []
        for prop in self.props:
            if prop.destroyed:
                continue
            dist = prop.pos.distance_to(pygame.Vector2(pos))
            if dist > radius:
                continue
            # A blast up at cruising altitude shouldn't pop cars in the street
            # below it: the vertical gap counts the same as the horizontal one.
            if abs(altitude - prop.type.height * 0.5) > radius:
                continue
            falloff = 1.0 - (dist / radius) * 0.6 if radius > 0 else 1.0
            if prop.take_damage(damage * falloff):
                self.props_destroyed += 1
                self.score += prop.type.score
                if prop.explosive:
                    chain.append(prop)

        if depth >= self.MAX_CHAIN_DEPTH:
            return
        for prop in chain:
            # A tank going up is a real explosion in its own right: it damages
            # blocks, sets off its neighbours, and can absolutely kill you.
            self.detonate(
                prop.pos,
                prop.type.height * 0.5,
                prop.type.blast_radius,
                prop.type.blast_damage,
                friendly=True,
                depth=depth + 1,
            )

    def _on_building_destroyed(self, building):
        self.blocks_destroyed += 1
        self.score += int(SCORE_BLOCK_BASE + building.height * SCORE_BLOCK_PER_METRE)
        # Only shout about round numbers -- a notification per block would be
        # constant noise once a bombing run gets going.
        if self.blocks_destroyed % 5 == 0:
            self.notify(f"{self.blocks_destroyed} blocks levelled")

    # ------------------------------------------------------------------ render

    def draw(self, surface, camera):
        """Same painter's-algorithm pass as World.draw, with props folded into
        the same Y-sort so a fuel tank in front of a block draws in front."""
        self._draw_ground(surface, camera)

        drawables = []
        for building in self.buildings:
            if camera.is_visible(building.rect.centerx, building.rect.centery, 400):
                drawables.append((building.rect.bottom, building))
        for prop in self.props:
            if camera.is_visible(prop.pos.x, prop.pos.y):
                drawables.append((prop.pos.y, prop))
        for projectile in self.projectiles:
            drawables.append((projectile.pos.y, projectile))
        if self.player is not None and self.player.alive:
            drawables.append((self.player.pos.y, self.player))

        drawables.sort(key=lambda item: item[0])
        for _, entity in drawables:
            entity.draw(surface, camera)

        for explosion in self.explosions:
            explosion.draw(surface, camera)
