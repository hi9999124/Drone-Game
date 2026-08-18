import pygame

from .. import constants
from ..utils import clamp
from .fonts import get_font

SCHEME_STICK = "Stick"
SCHEME_PADS = "Pads"
SCHEMES = [SCHEME_STICK, SCHEME_PADS]


class TouchControls:
    """On-screen controls for the full 2.5D control set.

    Reads real touches (FINGERDOWN/MOTION/UP, normalized 0..1 coords) and mouse
    clicks through the same path, so it behaves identically on a phone and on a
    desktop dev machine. Tracked per finger/pointer id rather than as flat
    booleans so several inputs can be held at once (steer + climb + fire).

    Two layouts, picked in Settings:

    * ``Stick`` (default) -- one floating analog joystick under the left thumb
      that both steers and throttles, a camera pad under the right thumb that
      pans the view to scout ahead, and FIRE/altitude buttons. This is the
      layout the game is designed around on a phone: a single thumb flies.
    * ``Pads`` -- the original six-button cross, kept because it maps 1:1 to
      the keyboard controls and some players prefer discrete buttons.

    ``state`` carries the button booleans plus two analog entries, ``stick``
    and ``look``, each an (x, y) pair in -1..1 screen space.
    """

    def __init__(self, scheme=SCHEME_STICK):
        self.scheme = scheme if scheme in SCHEMES else SCHEME_STICK
        self.buttons = {}
        self._pointers = {}
        self.state = {}
        self.radius = 40

        # Floating-joystick / camera-pad state. Each is claimed by whichever
        # pointer touched down inside its zone first and released on FINGERUP.
        self.stick_zone = pygame.Rect(0, 0, 0, 0)
        self.look_zone = pygame.Rect(0, 0, 0, 0)
        self.stick_radius = 70
        self.look_radius = 110
        self._stick_pointer = None
        self._stick_origin = pygame.Vector2()
        self._stick_vec = pygame.Vector2()
        self._look_pointer = None
        self._look_origin = pygame.Vector2()
        self._look_vec = pygame.Vector2()

        self.layout()

    def set_scheme(self, scheme):
        scheme = scheme if scheme in SCHEMES else SCHEME_STICK
        if scheme == self.scheme:
            return
        self.release_all()
        self.scheme = scheme
        self.layout()

    # ------------------------------------------------------------------ layout

    def layout(self):
        """Size and place the controls from the current surface size.

        Everything derives from the screen dimensions rather than fixed pixel
        constants, so the controls stay on-screen and stay thumb-sized whether
        that's a 1280x720 window or a phone in landscape.
        """
        if self.scheme == SCHEME_STICK:
            self._layout_stick()
        else:
            self._layout_pads()

        self.state = {key: False for key in self.buttons}
        self.state["stick"] = (0.0, 0.0)
        self.state["look"] = (0.0, 0.0)

    def _layout_stick(self):
        w, h = constants.WIDTH, constants.HEIGHT
        r = max(24, int(min(44, h * 0.085)))
        self.radius = r
        margin = max(14, int(w * 0.02))
        fire_r = int(r * 1.35)
        alt_r = int(r * 0.9)

        self.buttons = {
            "fire": pygame.Rect(0, 0, fire_r * 2, fire_r * 2),
            "ascend": pygame.Rect(0, 0, alt_r * 2, alt_r * 2),
            "descend": pygame.Rect(0, 0, alt_r * 2, alt_r * 2),
        }
        self._add_pause_button(r)
        base_y = h - margin - fire_r
        right_x = w - margin - fire_r
        self.buttons["fire"].center = (right_x, base_y)
        # Altitude stacked just inboard of FIRE, within the same thumb's reach.
        alt_x = right_x - fire_r - alt_r - 12
        self.buttons["ascend"].center = (alt_x, base_y - alt_r - 8)
        self.buttons["descend"].center = (alt_x, base_y + alt_r - int(alt_r * 0.6))

        # The joystick floats: it appears wherever the left thumb lands inside
        # this zone rather than at one fixed spot, which is what makes it
        # usable without looking at the screen.
        self.stick_radius = max(48, int(min(h * 0.17, w * 0.11)))
        self.stick_zone = pygame.Rect(0, int(h * 0.22), int(w * 0.5), int(h * 0.78))
        # Everything not spoken for by the joystick or the buttons pans the
        # camera -- deliberately generous, since a scouting swipe is coarse.
        self.look_zone = pygame.Rect(int(w * 0.5), 0, int(w * 0.5), h)
        self.look_radius = max(70, int(min(w, h) * 0.22))

    def _layout_pads(self):
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
        self._add_pause_button(r)

        self.stick_zone = pygame.Rect(0, 0, 0, 0)
        self.look_zone = pygame.Rect(0, 0, 0, 0)

    def _add_pause_button(self, r):
        """A phone has no ESC key, and the Android back button isn't something
        every device/ROM delivers reliably -- without this there is no way to
        pause, change loadout or leave a run from a touchscreen at all.

        Parked top-centre: the two top corners are already occupied by the
        HUD's flight and mission panels.
        """
        pause_r = max(16, int(r * 0.62))
        rect = pygame.Rect(0, 0, pause_r * 2, pause_r * 2)
        rect.center = (constants.WIDTH // 2, max(14, int(constants.HEIGHT * 0.03)) + pause_r)
        self.buttons["pause"] = rect

    # ------------------------------------------------------------------ input

    def _button_at(self, pos):
        for name, rect in self.buttons.items():
            # Circular hit test -- rect corners would make neighbouring buttons
            # overlap and steal each other's taps.
            center = pygame.Vector2(rect.center)
            if center.distance_to(pos) <= rect.width * 0.5:
                return name
        return None

    def handle_event(self, event):
        pointer_id, phase, pos = self._decode(event)
        if phase is None:
            return False

        if phase == "down":
            self._on_down(pointer_id, pos)
        elif phase == "motion":
            self._on_motion(pointer_id, pos)
        else:
            self._on_up(pointer_id)

        self._sync_state()
        return bool(self._pointers) or self._stick_pointer is not None

    def _decode(self, event):
        """Normalize finger and mouse events into (id, phase, position)."""
        if event.type == pygame.FINGERDOWN:
            return event.finger_id, "down", pygame.Vector2(
                event.x * constants.WIDTH, event.y * constants.HEIGHT
            )
        if event.type == pygame.FINGERMOTION:
            return event.finger_id, "motion", pygame.Vector2(
                event.x * constants.WIDTH, event.y * constants.HEIGHT
            )
        if event.type == pygame.FINGERUP:
            return event.finger_id, "up", None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return "mouse", "down", pygame.Vector2(event.pos)
        if event.type == pygame.MOUSEMOTION and event.buttons[0]:
            return "mouse", "motion", pygame.Vector2(event.pos)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            return "mouse", "up", None
        return None, None, None

    def _on_down(self, pointer_id, pos):
        button = self._button_at(pos)
        if button:
            self._pointers[pointer_id] = button
            return
        if self.scheme != SCHEME_STICK:
            return
        if self._stick_pointer is None and self.stick_zone.collidepoint(pos):
            self._stick_pointer = pointer_id
            self._stick_origin.update(pos)
            self._stick_vec.update(0, 0)
        elif self._look_pointer is None and self.look_zone.collidepoint(pos):
            self._look_pointer = pointer_id
            self._look_origin.update(pos)
            self._look_vec.update(0, 0)

    def _on_motion(self, pointer_id, pos):
        if pointer_id == self._stick_pointer:
            delta = pos - self._stick_origin
            if delta.length() > self.stick_radius:
                # Drag the base along with the thumb once it hits the rim, so a
                # long sweep keeps steering instead of pinning at full lock.
                self._stick_origin = pos - delta.normalize() * self.stick_radius
                delta = pos - self._stick_origin
            self._stick_vec.update(delta / self.stick_radius)
            return
        if pointer_id == self._look_pointer:
            delta = pos - self._look_origin
            self._look_vec.update(
                clamp(delta.x / self.look_radius, -1.0, 1.0),
                clamp(delta.y / self.look_radius, -1.0, 1.0),
            )
            return
        if pointer_id in self._pointers:
            button = self._button_at(pos)
            if button:
                self._pointers[pointer_id] = button
            else:
                self._pointers.pop(pointer_id, None)

    def _on_up(self, pointer_id):
        self._pointers.pop(pointer_id, None)
        if pointer_id == self._stick_pointer:
            self._stick_pointer = None
            self._stick_vec.update(0, 0)
        if pointer_id == self._look_pointer:
            self._look_pointer = None
            self._look_vec.update(0, 0)

    def _sync_state(self):
        active = set(self._pointers.values())
        for key in self.buttons:
            self.state[key] = key in active
        self.state["stick"] = (self._stick_vec.x, self._stick_vec.y)
        self.state["look"] = (self._look_vec.x, self._look_vec.y)

    def release_all(self):
        self._pointers.clear()
        self._stick_pointer = None
        self._look_pointer = None
        self._stick_vec.update(0, 0)
        self._look_vec.update(0, 0)
        for key in self.buttons:
            self.state[key] = False
        self.state["stick"] = (0.0, 0.0)
        self.state["look"] = (0.0, 0.0)

    # ----------------------------------------------------------------- render

    GLYPHS = {
        "left": "<",
        "right": ">",
        "thrust": "^",
        "reverse": "v",
        "ascend": "+",
        "descend": "-",
        "fire": "FIRE",
        "pause": "II",
    }

    def draw(self, surface):
        if self.scheme == SCHEME_STICK:
            self._draw_stick(surface)
            self._draw_look(surface)
        self._draw_buttons(surface)

    def _draw_buttons(self, surface):
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
            text = font.render(self.GLYPHS[name], True, text_color)
            surface.blit(text, text.get_rect(center=rect.center))

    def _draw_stick(self, surface):
        radius = self.stick_radius
        if self._stick_pointer is None:
            # Resting hint, parked where the thumb naturally sits, so the
            # control is discoverable before it's ever touched.
            center = pygame.Vector2(
                self.stick_zone.x + radius + max(14, int(constants.WIDTH * 0.03)),
                self.stick_zone.bottom - radius - max(14, int(constants.HEIGHT * 0.04)),
            )
            ring = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*constants.ACCENT_DIM, 70), (radius, radius), radius, width=2)
            pygame.draw.circle(ring, (*constants.ACCENT_DIM, 55), (radius, radius), int(radius * 0.36))
            surface.blit(ring, (center.x - radius, center.y - radius))
            label = get_font(12, mono=True).render("FLY", True, constants.TEXT_FAINT)
            surface.blit(label, label.get_rect(center=(center.x, center.y + radius + 12)))
            return

        center = self.stick_origin_pixels
        base = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(base, (*constants.PANEL_BG, 120), (radius, radius), radius)
        pygame.draw.circle(base, (*constants.ACCENT_DIM, 190), (radius, radius), radius, width=2)
        surface.blit(base, (center.x - radius, center.y - radius))

        knob = center + pygame.Vector2(self._stick_vec) * radius
        knob_r = int(radius * 0.38)
        pygame.draw.line(surface, constants.ACCENT_DIM, center, knob, 3)
        pygame.draw.circle(surface, constants.ACCENT, (int(knob.x), int(knob.y)), knob_r)
        pygame.draw.circle(surface, constants.TEXT_COLOR, (int(knob.x), int(knob.y)), knob_r, width=2)

    def _draw_look(self, surface):
        if self._look_pointer is None:
            # Sits clear of the HUD's top-right mission panel rather than
            # tucking under the top edge, where it would collide with it.
            hint = get_font(12, mono=True).render("DRAG TO LOOK", True, constants.TEXT_FAINT)
            surface.blit(hint, hint.get_rect(center=(self.look_zone.centerx, int(constants.HEIGHT * 0.28))))
            return
        origin = self._look_origin
        tip = origin + pygame.Vector2(self._look_vec) * self.look_radius
        pygame.draw.circle(surface, constants.ACCENT_DIM, (int(origin.x), int(origin.y)), 10, width=2)
        pygame.draw.line(surface, constants.ACCENT_DIM, origin, tip, 2)
        pygame.draw.circle(surface, constants.ACCENT, (int(tip.x), int(tip.y)), 7, width=2)

    @property
    def stick_origin_pixels(self):
        return pygame.Vector2(self._stick_origin)
