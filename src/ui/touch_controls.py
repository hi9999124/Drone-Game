import pygame

from .. import constants
from .fonts import get_font


class TouchControls:
    """On-screen controls for the full 2.5D control set.

    Reads real touches (FINGERDOWN/MOTION/UP, normalized 0..1 coords) and mouse
    clicks through the same path, so it behaves identically on a phone and on a
    desktop dev machine. Tracked per finger/pointer id rather than as flat
    booleans so several buttons can be held at once (thrust + turn + climb).
    """

    def __init__(self):
        self.buttons = {}
        self._pointers = {}
        self.state = {}
        self.radius = 40
        self.layout()

    def layout(self):
        """Size and place the pads from the current surface size.

        Everything derives from the screen dimensions rather than fixed pixel
        constants, so the pads stay on-screen and stay thumb-sized whether
        that's a 1280x720 window or a phone in landscape.
        """
        w, h = constants.WIDTH, constants.HEIGHT
        r = max(24, int(min(44, h * 0.085)))
        self.radius = r
        margin = max(14, int(w * 0.02))
        gap = r * 2 + 10
        fire_r = int(r * 1.15)

        size = r * 2
        self.buttons = {
            name: pygame.Rect(0, 0, size, size)
            for name in ("left", "right", "thrust", "reverse", "ascend", "descend")
        }
        self.buttons["fire"] = pygame.Rect(0, 0, fire_r * 2, fire_r * 2)

        # Left cluster: a cross for turning plus forward/reverse thrust.
        # base_x leaves exactly one gap of room so the left pad can't clip off
        # the edge of a narrow screen.
        base_x = margin + r + gap
        base_y = h - margin - r
        self.buttons["left"].center = (base_x - gap, base_y)
        self.buttons["right"].center = (base_x + gap, base_y)
        self.buttons["thrust"].center = (base_x, base_y - gap)
        self.buttons["reverse"].center = (base_x, base_y)

        # Right cluster: altitude pads, with FIRE inboard of them.
        right_x = w - margin - r
        self.buttons["ascend"].center = (right_x, base_y - gap)
        self.buttons["descend"].center = (right_x, base_y)
        self.buttons["fire"].center = (right_x - gap - fire_r, base_y - int(gap * 0.55))

        self.state = {key: False for key in self.buttons}

    def _button_at(self, pos):
        for name, rect in self.buttons.items():
            # Circular hit test -- rect corners would make neighbouring buttons
            # overlap and steal each other's taps.
            center = pygame.Vector2(rect.center)
            if center.distance_to(pos) <= rect.width * 0.5:
                return name
        return None

    def handle_event(self, event):
        if event.type == pygame.FINGERDOWN:
            pos = (event.x * constants.WIDTH, event.y * constants.HEIGHT)
            button = self._button_at(pos)
            if button:
                self._pointers[event.finger_id] = button
        elif event.type == pygame.FINGERMOTION:
            if event.finger_id in self._pointers:
                pos = (event.x * constants.WIDTH, event.y * constants.HEIGHT)
                button = self._button_at(pos)
                if button:
                    self._pointers[event.finger_id] = button
                else:
                    self._pointers.pop(event.finger_id, None)
        elif event.type == pygame.FINGERUP:
            self._pointers.pop(event.finger_id, None)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            button = self._button_at(event.pos)
            if button:
                self._pointers["mouse"] = button
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._pointers.pop("mouse", None)
        else:
            return False

        active = set(self._pointers.values())
        for key in self.state:
            self.state[key] = key in active
        return bool(active)

    def release_all(self):
        self._pointers.clear()
        for key in self.state:
            self.state[key] = False

    def draw(self, surface):
        glyphs = {
            "left": "<",
            "right": ">",
            "thrust": "^",
            "reverse": "v",
            "ascend": "+",
            "descend": "-",
            "fire": "FIRE",
        }
        for name, rect in self.buttons.items():
            active = self.state[name]
            radius = rect.width // 2
            fill = pygame.Surface((rect.width, rect.width), pygame.SRCALPHA)
            alpha = 160 if active else 90
            pygame.draw.circle(fill, (*constants.PANEL_BG, alpha), (radius, radius), radius)
            surface.blit(fill, rect.topleft)

            color = constants.ACCENT if active else constants.ACCENT_DIM
            if name == "fire":
                color = constants.WARN if active else (120, 84, 40)
            pygame.draw.circle(surface, color, rect.center, radius, width=3)

            font = get_font(max(12, int(radius * (0.45 if name == "fire" else 0.7))), bold=True)
            text_color = constants.TEXT_COLOR if active else constants.TEXT_DIM
            text = font.render(glyphs[name], True, text_color)
            surface.blit(text, text.get_rect(center=rect.center))
