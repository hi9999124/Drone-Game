import pygame

from .. import constants
from ..utils import lerp_color
from .fonts import get_font


class Button:
    # hover_progress animates 0..1 instead of snapping, so the highlight eases
    # in/out instead of flickering when the pointer crosses the edge of the rect.
    def __init__(self, rect, label, on_click, font_size=24, enabled=True, accent=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.font = get_font(font_size, bold=True)
        self.hover_progress = 0.0
        self.enabled = enabled
        self.accent = accent or constants.ACCENT

    def handle_event(self, event, mouse_pos):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse_pos):
                self.on_click()
                return True
        return False

    def update(self, mouse_pos, dt):
        target = 1.0 if (self.enabled and self.rect.collidepoint(mouse_pos)) else 0.0
        self.hover_progress += (target - self.hover_progress) * min(1.0, 12.0 * dt)

    def draw(self, surface):
        if not self.enabled:
            pygame.draw.rect(surface, (14, 16, 22), self.rect, border_radius=10)
            pygame.draw.rect(surface, (36, 40, 50), self.rect, width=1, border_radius=10)
            text = self.font.render(self.label, True, constants.TEXT_FAINT)
            surface.blit(text, text.get_rect(center=self.rect.center))
            return

        t = self.hover_progress
        bg = lerp_color(constants.PANEL_BG, (self.accent[0] // 4, self.accent[1] // 4, self.accent[2] // 4), t)
        border = lerp_color(constants.ACCENT_DIM, self.accent, t)
        text_color = lerp_color(constants.TEXT_DIM, constants.TEXT_COLOR, t)

        pygame.draw.rect(surface, bg, self.rect, border_radius=10)
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=10)
        text = self.font.render(self.label, True, text_color)
        surface.blit(text, text.get_rect(center=self.rect.center))


class OptionRow:
    """A settings row: label on the left, < value > cycler on the right."""

    def __init__(self, rect, label, values, get_index, on_change):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.values = values
        self.get_index = get_index
        self.on_change = on_change
        self.label_font = get_font(21, bold=True)
        self.value_font = get_font(21, bold=True)
        size = 34
        self.left_btn = pygame.Rect(self.rect.right - 250, self.rect.centery - size // 2, size, size)
        self.right_btn = pygame.Rect(self.rect.right - size, self.rect.centery - size // 2, size, size)
        self.hover_left = 0.0
        self.hover_right = 0.0

    def _cycle(self, step):
        index = (self.get_index() + step) % len(self.values)
        self.on_change(self.values[index])

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.left_btn.collidepoint(mouse_pos):
                self._cycle(-1)
                return True
            if self.right_btn.collidepoint(mouse_pos):
                self._cycle(1)
                return True
            # Tapping the row itself advances too -- much friendlier on a phone
            # than trying to hit a 34px arrow.
            if self.rect.collidepoint(mouse_pos):
                self._cycle(1)
                return True
        return False

    def update(self, mouse_pos, dt):
        rate = min(1.0, 12.0 * dt)
        self.hover_left += ((1.0 if self.left_btn.collidepoint(mouse_pos) else 0.0) - self.hover_left) * rate
        self.hover_right += ((1.0 if self.right_btn.collidepoint(mouse_pos) else 0.0) - self.hover_right) * rate

    def draw(self, surface):
        pygame.draw.rect(surface, constants.PANEL_BG, self.rect, border_radius=10)
        pygame.draw.rect(surface, constants.PANEL_EDGE, self.rect, width=1, border_radius=10)

        label = self.label_font.render(self.label, True, constants.TEXT_DIM)
        surface.blit(label, (self.rect.x + 18, self.rect.centery - label.get_height() // 2))

        value = str(self.values[self.get_index()])
        value_surf = self.value_font.render(value, True, constants.ACCENT)
        value_rect = value_surf.get_rect(
            center=((self.left_btn.right + self.right_btn.left) // 2, self.rect.centery)
        )
        surface.blit(value_surf, value_rect)

        for rect, glyph, hover in (
            (self.left_btn, "<", self.hover_left),
            (self.right_btn, ">", self.hover_right),
        ):
            color = lerp_color(constants.TEXT_FAINT, constants.ACCENT, hover)
            glyph_surf = self.value_font.render(glyph, True, color)
            surface.blit(glyph_surf, glyph_surf.get_rect(center=rect.center))
