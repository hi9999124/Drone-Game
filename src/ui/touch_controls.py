import pygame

from .. import constants


class TouchControls:
    # Reads both real touches (FINGERDOWN/MOTION/UP, normalized 0..1 coords)
    # and mouse clicks through the same code path, so this works identically
    # on a phone and on a desktop dev machine. Tracked per finger/pointer id
    # rather than as three flat booleans so two buttons can be held down at
    # once (e.g. thrust + turn), which a single "last touched button" model
    # would not allow.
    RADIUS = 46
    MARGIN = 28

    def __init__(self):
        self._layout()
        self._pointers = {}  # id (finger_id or "mouse") -> button name
        self.left = False
        self.right = False
        self.thrust = False

    def _layout(self):
        w, h = constants.WIDTH, constants.HEIGHT
        r = self.RADIUS
        m = self.MARGIN
        self.left_btn = pygame.Rect(0, 0, r * 2, r * 2)
        self.left_btn.center = (m + r, h - m - r)
        self.right_btn = pygame.Rect(0, 0, r * 2, r * 2)
        self.right_btn.center = (m + r * 2 + 24 + r, h - m - r)
        self.thrust_btn = pygame.Rect(0, 0, r * 2, r * 2)
        self.thrust_btn.center = (w - m - r, h - m - r)

    def _button_at(self, pos):
        if self.left_btn.collidepoint(pos):
            return "left"
        if self.right_btn.collidepoint(pos):
            return "right"
        if self.thrust_btn.collidepoint(pos):
            return "thrust"
        return None

    def handle_event(self, event):
        if event.type == pygame.FINGERDOWN:
            pos = (event.x * constants.WIDTH, event.y * constants.HEIGHT)
            button = self._button_at(pos)
            if button:
                self._pointers[event.finger_id] = button
        elif event.type == pygame.FINGERUP:
            self._pointers.pop(event.finger_id, None)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            button = self._button_at(event.pos)
            if button:
                self._pointers["mouse"] = button
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._pointers.pop("mouse", None)
        else:
            return

        active = set(self._pointers.values())
        self.left = "left" in active
        self.right = "right" in active
        self.thrust = "thrust" in active

    def draw(self, surface):
        for rect, glyph, active in (
            (self.left_btn, "<", self.left),
            (self.right_btn, ">", self.right),
            (self.thrust_btn, "^", self.thrust),
        ):
            fill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.circle(fill, (*constants.PANEL_BG, 150), rect.center, self.RADIUS)
            surface.blit(fill, (0, 0))

            ring_color = constants.ACCENT if active else constants.ACCENT_DIM
            pygame.draw.circle(surface, ring_color, rect.center, self.RADIUS, width=3)

            font = pygame.font.SysFont("arial", 34, bold=True)
            text = font.render(glyph, True, constants.TEXT_COLOR if active else constants.TEXT_DIM)
            surface.blit(text, text.get_rect(center=rect.center))
