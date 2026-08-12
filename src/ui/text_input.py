import pygame

from .. import constants
from .fonts import get_font


class TextInput:
    """A single-line text field. Pygame has no built-in widget for this --
    TEXTINPUT events give committed characters (composition-aware, so this
    works correctly with IME input too), while BACKSPACE has to be read from
    KEYDOWN separately since it never appears as a TEXTINPUT character."""

    def __init__(self, rect, placeholder="", password=False, max_length=24):
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.password = password
        self.max_length = max_length
        self.text = ""
        self.focused = False
        self._cursor_blink = 0.0

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(mouse_pos)
            if self.focused:
                pygame.key.start_text_input()
            return
        if not self.focused:
            return
        if event.type == pygame.TEXTINPUT:
            if len(self.text) < self.max_length:
                self.text += event.text
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self.focused = False

    def update(self, dt):
        self._cursor_blink = (self._cursor_blink + dt) % 1.0

    def draw(self, surface):
        bg = constants.PANEL_BG
        edge = constants.ACCENT if self.focused else constants.PANEL_EDGE
        pygame.draw.rect(surface, bg, self.rect, border_radius=8)
        pygame.draw.rect(surface, edge, self.rect, width=2, border_radius=8)

        font = get_font(20, mono=True)
        if self.text:
            shown = "*" * len(self.text) if self.password else self.text
            color = constants.TEXT_COLOR
        else:
            shown = self.placeholder
            color = constants.TEXT_FAINT
        text_surf = font.render(shown, True, color)
        surface.blit(text_surf, (self.rect.x + 12, self.rect.centery - text_surf.get_height() // 2))

        if self.focused and self._cursor_blink < 0.5:
            cursor_x = self.rect.x + 12 + (text_surf.get_width() if self.text else 0)
            pygame.draw.line(
                surface,
                constants.ACCENT,
                (cursor_x, self.rect.y + 8),
                (cursor_x, self.rect.bottom - 8),
                2,
            )
