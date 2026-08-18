from dataclasses import dataclass

import pygame

from .. import constants
from .base import draw_shadow


@dataclass(frozen=True)
class PropType:
    key: str
    name: str
    radius: float  # ground footprint radius
    height: float  # how far it stands off the ground, in altitude units
    hp: float
    # Secondary blast let off when it dies. A fuel tank is worth aiming at
    # precisely because it takes half a street with it; a parked car isn't.
    blast_radius: float
    blast_damage: float
    score: int
    body_color: tuple
    accent_color: tuple


PROP_TYPES = [
    PropType(
        key="fuel",
        name="Fuel tank",
        radius=34.0,
        height=46.0,
        hp=40.0,
        blast_radius=210.0,
        blast_damage=200.0,
        score=120,
        body_color=(96, 74, 48),
        accent_color=(255, 176, 66),
    ),
    PropType(
        key="tanker",
        name="Fuel tanker",
        radius=26.0,
        height=26.0,
        hp=28.0,
        blast_radius=170.0,
        blast_damage=150.0,
        score=90,
        body_color=(84, 78, 62),
        accent_color=(226, 150, 70),
    ),
    PropType(
        key="car",
        name="Car",
        radius=13.0,
        height=11.0,
        hp=12.0,
        blast_radius=52.0,
        blast_damage=26.0,
        score=25,
        body_color=(70, 76, 90),
        accent_color=(140, 152, 176),
    ),
    PropType(
        key="tower",
        name="Comms tower",
        radius=16.0,
        height=150.0,
        hp=55.0,
        blast_radius=70.0,
        blast_damage=40.0,
        score=80,
        body_color=(74, 80, 96),
        accent_color=(120, 200, 160),
    ),
]

PROPS_BY_KEY = {p.key: p for p in PROP_TYPES}


class Prop:
    """A small destructible object in the street: fuel tanks, cars, towers.

    Buildings are the sandbox's main course, but they're on a 420-unit grid --
    props are what fill the streets between them, and the explosive ones chain
    off each other, so a single well-placed bomb can take out a whole depot
    instead of one rectangle.
    """

    def __init__(self, x, y, prop_type):
        self.pos = pygame.Vector2(x, y)
        self.type = prop_type
        self.hp = prop_type.hp
        self.destroyed = False
        self.flash = 0.0  # brief hit feedback, seconds

    @property
    def explosive(self):
        return self.type.blast_damage >= 100.0

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)

    def contains_point(self, x, y):
        return self.pos.distance_to(pygame.Vector2(x, y)) <= self.type.radius

    def take_damage(self, amount):
        """Returns True on the hit that destroys it."""
        if self.destroyed:
            return False
        self.hp -= amount
        self.flash = 0.12
        if self.hp <= 0:
            self.hp = 0.0
            self.destroyed = True
            return True
        return False

    def draw(self, surface, camera):
        if self.destroyed:
            self._draw_wreck(surface, camera)
            return

        draw_shadow(surface, camera, self.pos, 0.0, self.type.radius)
        base = camera.to_screen(self.pos.x, self.pos.y, 0.0)
        top = camera.to_screen(self.pos.x, self.pos.y, self.type.height)
        radius = int(self.type.radius)
        body = self.type.body_color if self.flash <= 0.0 else constants.TEXT_COLOR

        if self.type.key == "tower":
            # A lattice mast reads as height: two legs plus a couple of rungs.
            pygame.draw.line(surface, body, (base[0] - radius, base[1]), top, 2)
            pygame.draw.line(surface, body, (base[0] + radius, base[1]), top, 2)
            for step in (0.35, 0.7):
                y = base[1] + (top[1] - base[1]) * step
                half = radius * (1.0 - step)
                pygame.draw.line(surface, self.type.accent_color, (base[0] - half, y), (base[0] + half, y), 1)
            pygame.draw.circle(surface, constants.DANGER, (int(top[0]), int(top[1])), 3)
            return

        # Everything else is an extruded box/cylinder: a body quad from the
        # ground up to its height, capped with a lit top face.
        rect = pygame.Rect(base[0] - radius, top[1], radius * 2, max(2, base[1] - top[1]))
        pygame.draw.rect(surface, body, rect, border_radius=3)
        pygame.draw.ellipse(
            surface,
            self.type.accent_color if self.explosive else (96, 104, 122),
            (base[0] - radius, top[1] - radius * 0.35, radius * 2, radius * 0.7),
        )
        pygame.draw.rect(surface, self.type.accent_color, rect, width=1, border_radius=3)

    def _draw_wreck(self, surface, camera):
        base = camera.to_screen(self.pos.x, self.pos.y, 0.0)
        radius = int(self.type.radius)
        scorch = pygame.Surface((radius * 4, radius * 3), pygame.SRCALPHA)
        pygame.draw.ellipse(scorch, (0, 0, 0, 110), scorch.get_rect())
        surface.blit(scorch, (base[0] - radius * 2, base[1] - radius * 1.5))
        pygame.draw.ellipse(
            surface, constants.RUBBLE, (base[0] - radius, base[1] - radius * 0.4, radius * 2, radius * 0.8)
        )
