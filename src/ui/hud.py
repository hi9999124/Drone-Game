import pygame

from .. import constants


class HUD:
    def __init__(self):
        self.value_font = pygame.font.SysFont("consolas", 18)
        self.label_font = pygame.font.SysFont("consolas", 13)

    def draw(self, surface, drone):
        panel = pygame.Rect(20, 20, 220, 74)
        panel_surf = pygame.Surface(panel.size, pygame.SRCALPHA)
        panel_surf.fill((*constants.PANEL_BG, 190))
        surface.blit(panel_surf, panel.topleft)
        pygame.draw.rect(surface, constants.ACCENT_DIM, panel, width=1, border_radius=8)

        speed = drone.vel.length()
        speed_text = self.value_font.render(f"SPEED  {speed:6.0f} u/s", True, constants.TEXT_COLOR)
        surface.blit(speed_text, (panel.x + 14, panel.y + 10))

        bar_rect = pygame.Rect(panel.x + 14, panel.y + 40, panel.width - 28, 10)
        pygame.draw.rect(surface, (40, 44, 56), bar_rect, border_radius=4)
        fill_width = int(bar_rect.width * drone.throttle)
        if fill_width > 0:
            pygame.draw.rect(
                surface, constants.ACCENT, (bar_rect.x, bar_rect.y, fill_width, bar_rect.height), border_radius=4
            )

        label = self.label_font.render("THROTTLE", True, constants.TEXT_DIM)
        surface.blit(label, (panel.x + 14, panel.y + 54))
