"""Drives the real Game state machine headlessly: menus -> Free Flight -> result.

Run with: python tests/smoke_game.py   (needs pygame, no display required)
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile

import pygame

from src import game as game_module
from src import save_system

save_system.SAVE_PATH = os.path.join(tempfile.mkdtemp(), "savegame.json")

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name + ("   " + str(detail) if detail else ""))
    if not condition:
        failures.append(name)


game = game_module.Game()
check("boots into the menu", game.state == game_module.STATE_MENU)

game._open_mode_select()
check("mode select has 5 cards", len(game.mode_select_menu.cards) == 5, len(game.mode_select_menu.cards))
labels = [label for _rect, label, _cb, _color in game.mode_select_menu.cards]
check("Free Flight is offered", "FREE FLIGHT" in labels, labels)
check("cards fit on screen", all(r.right <= game_module.constants.WIDTH for r, *_ in game.mode_select_menu.cards))

game._open_sandbox_select()
check("airframe picker opens", game.state == game_module.STATE_SANDBOX_SELECT)

game._start_sandbox_session("fpv")
check("free flight starts", game.state == game_module.STATE_PLAYING and game.world.mode == "sandbox")

# Fly for a few seconds through the real update/draw path.
for _ in range(240):
    game._update(1 / 60)
    game._draw()
check("still flying, no result screen", game.state == game_module.STATE_PLAYING)

game._handle_escape()
check("escape pauses", game.state == game_module.STATE_PAUSED)
game._draw()

game._open_loadout_select()
check("pause -> change loadout reopens the picker", game.state == game_module.STATE_SANDBOX_SELECT)
game._close_sandbox_select()
check("back returns to the pause screen", game.state == game_module.STATE_PAUSED)

coins_before = game.profile["coins"]
xp_before = game.profile["xp"]
career_before = game.profile["total_score"]
game._return_to_menu()
check("leaving ends the run on a summary", game.state == game_module.STATE_RESULT)
check("sandbox pays no coins", game.profile["coins"] == coins_before)
check("sandbox pays no xp", game.profile["xp"] == xp_before)
check("sandbox does not touch career score", game.profile["total_score"] == career_before)
game._draw()

game._return_to_menu()
check("summary -> main menu", game.state == game_module.STATE_MENU and game.world is None)

# Other modes still start and draw.
game._start_mission("fpv")
for _ in range(60):
    game._update(1 / 60)
    game._draw()
check("strike mission still runs", game.world.mode == "strike")
game._return_to_menu()

game._start_defense_mission("aagun")
for _ in range(60):
    game._update(1 / 60)
    game._draw()
check("defense mission still runs", game.world.mode == "defense")
game._return_to_menu()

game._start_survival_mission()
for _ in range(60):
    game._update(1 / 60)
    game._draw()
check("survival mission still runs", game.world.mode == "survival")
game._return_to_menu()

# Settings screens render and the touch layout option applies live.
game.settings["touch_controls"] = "On"
game._open_settings()
game._draw()
game.settings["touch_scheme"] = "Pads"
game._on_settings_changed("touch_scheme")
check("touch layout switches to pads", game.touch.scheme == "Pads")
game.settings["touch_scheme"] = "Stick"
game._on_settings_changed("touch_scheme")
check("touch layout switches back to stick", game.touch.scheme == "Stick")
game._close_settings()

game._open_howto()
game._draw()
check("how to play renders", game.state == game_module.STATE_HOWTO)
game._close_howto()

# Touch controls draw over a live sandbox run at a phone-ish resolution.
game_module.constants.WIDTH, game_module.constants.HEIGHT = 2340, 1080
game.screen = pygame.display.set_mode((2340, 1080))
game._reflow_for_resolution()
game._start_sandbox_session("baba")
for _ in range(60):
    game._update(1 / 60)
    game._draw()
check("renders at a phone resolution with touch on", game.state == game_module.STATE_PLAYING)
check("touch buttons stay on screen", all(r.right <= 2340 and r.bottom <= 1080 for r in game.touch.buttons.values()))

# The on-screen pause button is the only way off a touchscreen into the menu.
pause_rect = game.touch.buttons["pause"]
game._handle_events(1 / 60)  # drain
pygame.event.post(
    pygame.event.Event(
        pygame.FINGERDOWN,
        {
            "finger_id": 9,
            "x": pause_rect.centerx / game_module.constants.WIDTH,
            "y": pause_rect.centery / game_module.constants.HEIGHT,
            "dx": 0,
            "dy": 0,
            "touch_id": 0,
        },
    )
)
game._handle_events(1 / 60)
check("on-screen pause button pauses", game.state == game_module.STATE_PAUSED, game.state)
game._resume()

pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_AC_BACK, "mod": 0, "unicode": "", "scancode": 0}))
game._handle_events(1 / 60)
check("android back button pauses", game.state == game_module.STATE_PAUSED, game.state)

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("all checks passed")
