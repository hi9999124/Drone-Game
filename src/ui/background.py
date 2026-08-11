import pygame

from .. import constants


def draw_grid(surface, spacing=48):
    width, height = surface.get_size()
    for x in range(0, width, spacing):
        pygame.draw.line(surface, constants.GRID_COLOR, (x, 0), (x, height))
    for y in range(0, height, spacing):
        pygame.draw.line(surface, constants.GRID_COLOR, (0, y), (width, y))
