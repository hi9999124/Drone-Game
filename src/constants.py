WIDTH, HEIGHT = 1280, 720
# The windowed-mode design resolution. WIDTH/HEIGHT above get overwritten at
# runtime to the real display size when fullscreen is toggled on (so every
# menu/HUD coordinate, which is computed fresh off WIDTH/HEIGHT, lays out
# sharply at native resolution instead of a blurry stretched 1280x720) --
# these two stay fixed so toggling fullscreen back off knows what to restore.
WINDOWED_WIDTH, WINDOWED_HEIGHT = WIDTH, HEIGHT
FPS = 60

# --- World / 2.5D projection -------------------------------------------------
# The world is a flat XY plane seen from above, plus an altitude axis (Z).
# Z_SCALE is how many screen pixels one unit of altitude lifts a sprite upward:
# that vertical offset, plus a ground shadow, is what sells "2.5D" without any
# real 3D maths.
WORLD_SIZE = 4200.0
MAX_ALTITUDE = 230.0
Z_SCALE = 0.62

# --- Palette -----------------------------------------------------------------
BG_COLOR = (9, 11, 16)
GROUND_COLOR = (19, 23, 31)
GRID_COLOR = (27, 32, 43)

ACCENT = (56, 214, 255)
ACCENT_DIM = (30, 100, 120)
WARN = (255, 176, 66)
DANGER = (255, 74, 92)
GOOD = (110, 231, 160)

DRONE_COLOR = (150, 235, 255)
TEXT_COLOR = (230, 236, 245)
TEXT_DIM = (140, 150, 165)
TEXT_FAINT = (92, 100, 116)

PANEL_BG = (18, 21, 30)
PANEL_EDGE = (44, 51, 66)
OVERLAY = (5, 6, 10, 205)

BUILDING_WALL = (38, 42, 54)
BUILDING_WALL_LIT = (48, 53, 67)
BUILDING_ROOF = (55, 61, 76)
TARGET_WALL = (86, 44, 48)
TARGET_ROOF = (112, 58, 62)
PROTECTED_WALL = (44, 72, 58)
PROTECTED_ROOF = (58, 94, 76)
SHELTER_WALL = (34, 54, 74)
SHELTER_ROOF = (46, 72, 98)
WINDOW_DARK = (21, 24, 32)
WINDOW_LIT = (92, 102, 122)
RUBBLE = (30, 32, 38)

ENEMY_COLOR = (255, 120, 130)
ENEMY_DIM = (150, 60, 70)
