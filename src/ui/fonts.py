import pygame

# pygame.font.SysFont() re-reads and re-rasterizes the font every call, which is
# far too slow to do inside a draw loop. Everything goes through this cache
# instead so each (size, bold, mono) combination is built exactly once.
_cache = {}


def get_font(size, bold=False, mono=False):
    key = (size, bold, mono)
    font = _cache.get(key)
    if font is None:
        name = "consolas,dejavusansmono,couriernew" if mono else "arial,dejavusans,freesans"
        font = pygame.font.SysFont(name, size, bold=bold)
        _cache[key] = font
    return font
