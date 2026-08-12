import random

import pygame

from .. import constants
from ..utils import clamp


class Building:
    """An abandoned apartment block: a footprint rectangle plus a height.

    Drawn as a roof quad and a front wall, which in this projection is all that
    is ever visible (side walls are edge-on and have zero screen width). The
    window grid on the front wall is generated once at construction and cached,
    so the per-frame cost stays a couple of blits.
    """

    def __init__(self, x, y, width, depth, height, is_target=False, is_protected=False):
        self.rect = pygame.Rect(int(x), int(y), int(width), int(depth))
        self.height = float(height)
        self.is_target = is_target
        # is_protected: the Air Defense mode's inverse of is_target -- a
        # civilian structure raiders are trying to destroy and the player is
        # trying to keep standing, rather than something the player attacks.
        self.is_protected = is_protected
        self.max_hp = 260.0 if (is_target or is_protected) else 0.0
        self.hp = self.max_hp
        self.destroyed = False
        self._windows = self._generate_windows()

    @property
    def center(self):
        return pygame.Vector2(self.rect.centerx, self.rect.centery)

    def _generate_windows(self):
        """Pick a window grid + which panes are broken/lit. Done once, not per frame."""
        rng = random.Random((self.rect.x * 73856093) ^ (self.rect.y * 19349663))
        cols = max(2, int(self.rect.width // 26))
        rows = max(2, int(self.height // 24))
        return [
            [rng.random() for _ in range(cols)]
            for _ in range(rows)
        ], rng.random()

    def contains_point(self, x, y):
        return self.rect.collidepoint(x, y)

    def blocks_at(self, x, y, altitude):
        """True if this building occupies the given point in 3D space."""
        if self.destroyed:
            return False
        return altitude < self.height and self.rect.collidepoint(x, y)

    def take_damage(self, amount):
        if not (self.is_target or self.is_protected) or self.destroyed:
            return False
        self.hp -= amount
        if self.hp <= 0:
            self.destroyed = True
            return True
        return False

    def draw(self, surface, camera):
        if self.destroyed:
            self._draw_rubble(surface, camera)
            return

        left, top = camera.to_screen(self.rect.left, self.rect.top, 0.0)
        right, bottom = camera.to_screen(self.rect.right, self.rect.bottom, 0.0)
        lift = self.height * constants.Z_SCALE

        if self.is_target:
            wall_color, roof_color = constants.TARGET_WALL, constants.TARGET_ROOF
        elif self.is_protected:
            wall_color, roof_color = constants.PROTECTED_WALL, constants.PROTECTED_ROOF
        else:
            wall_color, roof_color = constants.BUILDING_WALL, constants.BUILDING_ROOF

        # Front wall: the face between the near (bottom) edge and the roofline.
        wall_rect = pygame.Rect(int(left), int(bottom - lift), int(right - left), int(lift))
        if wall_rect.height > 0:
            pygame.draw.rect(surface, wall_color, wall_rect)
            self._draw_windows(surface, wall_rect)

        # Roof: the footprint, lifted by the building's height.
        roof_points = [
            (left, top - lift),
            (right, top - lift),
            (right, bottom - lift),
            (left, bottom - lift),
        ]
        pygame.draw.polygon(surface, roof_color, roof_points)
        pygame.draw.polygon(surface, constants.PANEL_EDGE, roof_points, width=1)

        if self.is_target:
            self._draw_target_marker(surface, roof_points, left, right, top, lift)
        elif self.is_protected:
            self._draw_protected_marker(surface, roof_points, left, right, top, lift)

    def _draw_windows(self, surface, wall_rect):
        grid, seed = self._windows
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if not rows or not cols:
            return
        pad_x = 6
        cell_w = (wall_rect.width - pad_x * 2) / cols
        cell_h = wall_rect.height / rows
        if cell_w < 3 or cell_h < 4:
            return
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                # Mostly dark (abandoned); a few panes catch light.
                color = constants.WINDOW_LIT if value > 0.88 else constants.WINDOW_DARK
                wx = wall_rect.left + pad_x + col * cell_w + cell_w * 0.18
                wy = wall_rect.top + row * cell_h + cell_h * 0.22
                pygame.draw.rect(
                    surface,
                    color,
                    (int(wx), int(wy), max(2, int(cell_w * 0.64)), max(2, int(cell_h * 0.5))),
                )

    def _draw_target_marker(self, surface, roof_points, left, right, top, lift):
        cx = (left + right) * 0.5
        cy = top - lift
        pygame.draw.polygon(surface, constants.DANGER, roof_points, width=2)
        size = 9
        pygame.draw.line(surface, constants.DANGER, (cx - size, cy), (cx + size, cy), 2)
        pygame.draw.line(surface, constants.DANGER, (cx, cy - size), (cx, cy + size), 2)

        # Health bar above the roof once it has taken a hit.
        if self.hp < self.max_hp:
            bar_w = max(40, (right - left) * 0.7)
            bar_x = cx - bar_w * 0.5
            bar_y = cy - 22
            pygame.draw.rect(surface, (40, 20, 24), (bar_x, bar_y, bar_w, 5))
            frac = clamp(self.hp / self.max_hp, 0.0, 1.0)
            pygame.draw.rect(surface, constants.DANGER, (bar_x, bar_y, bar_w * frac, 5))

    def _draw_protected_marker(self, surface, roof_points, left, right, top, lift):
        cx = (left + right) * 0.5
        cy = top - lift
        pygame.draw.polygon(surface, constants.GOOD, roof_points, width=2)
        size = 9
        shield = [
            (cx, cy - size),
            (cx + size * 0.8, cy - size * 0.4),
            (cx + size * 0.6, cy + size * 0.7),
            (cx, cy + size),
            (cx - size * 0.6, cy + size * 0.7),
            (cx - size * 0.8, cy - size * 0.4),
        ]
        pygame.draw.polygon(surface, constants.GOOD, shield, width=2)

        if self.hp < self.max_hp:
            bar_w = max(40, (right - left) * 0.7)
            bar_x = cx - bar_w * 0.5
            bar_y = cy - 22
            pygame.draw.rect(surface, (18, 34, 26), (bar_x, bar_y, bar_w, 5))
            frac = clamp(self.hp / self.max_hp, 0.0, 1.0)
            pygame.draw.rect(surface, constants.GOOD, (bar_x, bar_y, bar_w * frac, 5))

    def _draw_rubble(self, surface, camera):
        left, top = camera.to_screen(self.rect.left, self.rect.top, 0.0)
        right, bottom = camera.to_screen(self.rect.right, self.rect.bottom, 0.0)
        pygame.draw.rect(
            surface, constants.RUBBLE, (int(left), int(top), int(right - left), int(bottom - top))
        )
        rng = random.Random(self.rect.x ^ self.rect.y)
        for _ in range(10):
            px = rng.uniform(left, right)
            py = rng.uniform(top, bottom)
            pygame.draw.rect(surface, (44, 46, 52), (int(px), int(py), 5, 4))
