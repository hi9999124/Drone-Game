import pygame

from .. import constants
from ..utils import lerp_color


class Button:
    # hover_progress animates 0..1 instead of snapping, so the highlight eases
    # in/out instead of flickering when the mouse crosses the edge of the rect.
    def __init__(self, rect, label, on_click, font=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.font = font or pygame.font.SysFont("arial", 26, bold=True)
        self.hover_progress = 0.0

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse_pos):
                self.on_click()

    def update(self, mouse_pos, dt):
        target = 1.0 if self.rect.collidepoint(mouse_pos) else 0.0
        self.hover_progress += (target - self.hover_progress) * min(1.0, 12.0 * dt)

    def draw(self, surface):
        t = self.hover_progress
        bg = lerp_color(constants.PANEL_BG, constants.ACCENT_DIM, t)
        border = lerp_color(constants.ACCENT_DIM, constants.ACCENT, t)
        text_color = lerp_color(constants.TEXT_DIM, constants.TEXT_COLOR, t)

        pygame.draw.rect(surface, bg, self.rect, border_radius=10)
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=10)

        text_surf = self.font.render(self.label, True, text_color)
        surface.blit(text_surf, text_surf.get_rect(center=self.rect.center))
