import pygame

from .. import constants
from .button import Button


class MainMenu:
    def __init__(self, on_play, on_quit):
        cx = constants.WIDTH // 2
        self.title_font = pygame.font.SysFont("arial", 64, bold=True)
        self.subtitle_font = pygame.font.SysFont("arial", 22)
        self.hint_font = pygame.font.SysFont("consolas", 18)
        self.buttons = [
            Button((cx - 110, 340, 220, 56), "PLAY", on_play),
            Button((cx - 110, 410, 220, 56), "QUIT", on_quit),
        ]

    def handle_event(self, event, mouse_pos):
        for button in self.buttons:
            button.handle_event(event, mouse_pos)

    def update(self, mouse_pos, dt):
        for button in self.buttons:
            button.update(mouse_pos, dt)

    def draw(self, surface):
        title = self.title_font.render("DRONE / PVO", True, constants.ACCENT)
        surface.blit(title, title.get_rect(center=(constants.WIDTH // 2, 200)))

        subtitle = self.subtitle_font.render(
            "pilot a drone through the arena", True, constants.TEXT_DIM
        )
        surface.blit(subtitle, subtitle.get_rect(center=(constants.WIDTH // 2, 250)))

        for button in self.buttons:
            button.draw(surface)

        hint = self.hint_font.render(
            "WASD / Arrow keys to fly   -   ESC to pause", True, constants.TEXT_DIM
        )
        surface.blit(hint, hint.get_rect(center=(constants.WIDTH // 2, constants.HEIGHT - 40)))


class PauseMenu:
    def __init__(self, on_resume, on_main_menu, on_quit):
        cx, cy = constants.WIDTH // 2, constants.HEIGHT // 2
        self.title_font = pygame.font.SysFont("arial", 40, bold=True)
        self.overlay = pygame.Surface((constants.WIDTH, constants.HEIGHT), pygame.SRCALPHA)
        self.overlay.fill(constants.OVERLAY)
        self.buttons = [
            Button((cx - 110, cy - 20, 220, 52), "RESUME", on_resume),
            Button((cx - 110, cy + 44, 220, 52), "MAIN MENU", on_main_menu),
            Button((cx - 110, cy + 108, 220, 52), "QUIT", on_quit),
        ]

    def handle_event(self, event, mouse_pos):
        for button in self.buttons:
            button.handle_event(event, mouse_pos)

    def update(self, mouse_pos, dt):
        for button in self.buttons:
            button.update(mouse_pos, dt)

    def draw(self, surface):
        surface.blit(self.overlay, (0, 0))
        title = self.title_font.render("PAUSED", True, constants.TEXT_COLOR)
        surface.blit(title, title.get_rect(center=(constants.WIDTH // 2, constants.HEIGHT // 2 - 90)))
        for button in self.buttons:
            button.draw(surface)
