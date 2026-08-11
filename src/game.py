import sys

import pygame

from . import constants
from .drone import Drone
from .ui.background import draw_grid
from .ui.hud import HUD
from .ui.menu import MainMenu, PauseMenu

STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Drone / PVO")
        self.screen = pygame.display.set_mode((constants.WIDTH, constants.HEIGHT))
        self.clock = pygame.time.Clock()

        self.running = True
        self.state = STATE_MENU
        self.drone = None

        self.main_menu = MainMenu(self._start_game, self._quit)
        self.pause_menu = PauseMenu(self._resume, self._return_to_menu, self._quit)
        self.hud = HUD()

    def run(self):
        while self.running:
            dt = self.clock.tick(constants.FPS) / 1000.0
            self._handle_events(dt)
            self._update(dt)
            self._draw()
        pygame.quit()
        sys.exit()

    def _start_game(self):
        self.drone = Drone(constants.WIDTH / 2, constants.HEIGHT / 2)
        self.state = STATE_PLAYING

    def _resume(self):
        self.state = STATE_PLAYING

    def _return_to_menu(self):
        self.drone = None
        self.state = STATE_MENU

    def _quit(self):
        self.running = False

    def _handle_events(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.state == STATE_PLAYING:
                    self.state = STATE_PAUSED
                elif self.state == STATE_PAUSED:
                    self.state = STATE_PLAYING

            if self.state == STATE_MENU:
                self.main_menu.handle_event(event, mouse_pos)
            elif self.state == STATE_PAUSED:
                self.pause_menu.handle_event(event, mouse_pos)

    def _update(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        if self.state == STATE_MENU:
            self.main_menu.update(mouse_pos, dt)
        elif self.state == STATE_PLAYING:
            keys = pygame.key.get_pressed()
            self.drone.handle_input(keys, dt)
            self.drone.update(dt, (constants.WIDTH, constants.HEIGHT))
        elif self.state == STATE_PAUSED:
            self.pause_menu.update(mouse_pos, dt)

    def _draw(self):
        self.screen.fill(constants.BG_COLOR)
        draw_grid(self.screen)

        if self.state == STATE_MENU:
            self.main_menu.draw(self.screen)
        elif self.state == STATE_PLAYING:
            self.drone.draw(self.screen)
            self.hud.draw(self.screen, self.drone)
        elif self.state == STATE_PAUSED:
            self.drone.draw(self.screen)
            self.hud.draw(self.screen, self.drone)
            self.pause_menu.draw(self.screen)

        pygame.display.flip()
