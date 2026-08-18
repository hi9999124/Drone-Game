"""Headless checks for Free Flight + the joystick touch scheme.

Run with: python tests/smoke_sandbox.py   (needs pygame, no display required)
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

pygame.init()
screen = pygame.display.set_mode((1280, 720))

from src import constants, drones
from src.camera import Camera
from src.sandbox_world import SandboxWorld
from src.ui.hud import HUD
from src.ui.touch_controls import SCHEME_PADS, SCHEME_STICK, TouchControls

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name + ("   " + str(detail) if detail else ""))
    if not condition:
        failures.append(name)


# ---------------------------------------------------------------- world setup
world = SandboxWorld(drones.get("fpv"), "Normal", seed=7)
check("city generated", len(world.buildings) > 40, len(world.buildings))
check("props generated", len(world.props) > 30, len(world.props))
check("every block destructible", all(b.max_hp > 0 for b in world.buildings))
check("no hostiles", not world.enemies and not world.pvo_units)
check("no mission targets", not world.targets)

# ------------------------------------------------------- ram a block down
target = min(
    (b for b in world.buildings if b.height <= 110),
    key=lambda b: b.center.distance_to(world.player.pos),
)
player = world.player
player.pos.update(target.center.x, target.center.y - 400)
player.altitude = target.height - 20
player.angle = 90.0  # facing +y, toward the block
controls = {"thrust": True}
for _ in range(400):
    world.update(1 / 60, controls)
    if target.destroyed:
        break
check("kamikaze levels a block", target.destroyed, f"hp={target.hp}")
check("score awarded", world.score > 0, world.score)
check("blocks_destroyed counted", world.blocks_destroyed >= 1, world.blocks_destroyed)
check("airframe lost but respawns", world.airframes_lost >= 1, world.airframes_lost)

for _ in range(120):
    world.update(1 / 60, {})
check("respawned after crash", world.player is not None and world.player.alive)
check("no result -- sandbox never ends", world.result == "playing", world.result)

# ------------------------------------------------------------- fuel chaining
chain_world = SandboxWorld(drones.get("baba"), "Normal", seed=3)
fuel = [p for p in chain_world.props if p.type.key in ("fuel", "tanker")]
check("fuel props exist", len(fuel) > 10, len(fuel))
before = chain_world.props_destroyed
chain_world.detonate(fuel[0].pos, fuel[0].type.height * 0.5, 60.0, 90.0)
check("blast destroys props", chain_world.props_destroyed > before, chain_world.props_destroyed - before)

# ------------------------------------------------------------------- rearming
rearm_world = SandboxWorld(drones.get("hornet"), "Normal", seed=11)
rearm_world.player.ammo = 0
for _ in range(int(60 * 3.0)):
    rearm_world.update(1 / 60, {})
check("ordnance trickles back", rearm_world.player.ammo >= 1, rearm_world.player.ammo)

# ------------------------------------- stick steering turns the drone around
stick_world = SandboxWorld(drones.get("hornet"), "Normal", seed=5)
stick_world.player.angle = 0.0  # facing +x
stick_world.player.pos.update(0, 0)
for _ in range(90):
    stick_world.update(1 / 60, {"stick": (0.0, 1.0)})  # push "down" the screen
angle = stick_world.player.angle % 360
check("stick steers to the pushed heading", abs(angle - 90.0) < 12.0, angle)
check("stick also throttles up", stick_world.player.speed > 50.0, stick_world.player.speed)

# ---------------------------------------------------------------- HUD + draw
camera = Camera()
camera.snap_to(world.player.pos)
hud = HUD()
world.draw(screen, camera)
hud.draw(screen, world, camera, show_fps=True, fps=60.0)
check("world + HUD render", True)

# ------------------------------------------------------------ touch controls
touch = TouchControls(scheme=SCHEME_STICK)
check("stick scheme buttons", set(touch.buttons) == {"fire", "ascend", "descend", "pause"}, sorted(touch.buttons))

down = pygame.event.Event(
    pygame.FINGERDOWN, {"finger_id": 1, "x": 0.18, "y": 0.75, "dx": 0, "dy": 0, "touch_id": 0}
)
move = pygame.event.Event(
    pygame.FINGERMOTION, {"finger_id": 1, "x": 0.18, "y": 0.95, "dx": 0, "dy": 0.2, "touch_id": 0}
)
touch.handle_event(down)
touch.handle_event(move)
sx, sy = touch.state["stick"]
check("joystick reports deflection", sy > 0.5 and abs(sx) < 0.2, (sx, sy))

look_down = pygame.event.Event(
    pygame.FINGERDOWN, {"finger_id": 2, "x": 0.7, "y": 0.4, "dx": 0, "dy": 0, "touch_id": 0}
)
look_move = pygame.event.Event(
    pygame.FINGERMOTION, {"finger_id": 2, "x": 0.85, "y": 0.4, "dx": 0.15, "dy": 0, "touch_id": 0}
)
touch.handle_event(look_down)
touch.handle_event(look_move)
lx, ly = touch.state["look"]
check("camera pad reports pan", lx > 0.5 and abs(ly) < 0.1, (lx, ly))

fire_down = pygame.event.Event(
    pygame.FINGERDOWN,
    {
        "finger_id": 3,
        "x": touch.buttons["fire"].centerx / constants.WIDTH,
        "y": touch.buttons["fire"].centery / constants.HEIGHT,
        "dx": 0,
        "dy": 0,
        "touch_id": 0,
    },
)
touch.handle_event(fire_down)
check("fire button + stick held together", touch.state["fire"] and touch.state["stick"][1] > 0.5)

touch.handle_event(pygame.event.Event(pygame.FINGERUP, {"finger_id": 1, "x": 0.18, "y": 0.95, "touch_id": 0}))
check("stick recentres on release", touch.state["stick"] == (0.0, 0.0), touch.state["stick"])

touch.draw(screen)
touch.set_scheme(SCHEME_PADS)
check("pads scheme restores old buttons", "thrust" in touch.buttons and "left" in touch.buttons)
touch.draw(screen)
touch.release_all()

# ------------------------------------------------------------- camera look
cam = Camera()
cam.snap_to(pygame.Vector2(0, 0))
base = cam.to_screen(0, 0, 0)
cam.set_look((1.0, 0.0))
for _ in range(60):
    cam.update(1 / 60)
panned = cam.to_screen(0, 0, 0)
check("free look pans the view", base[0] - panned[0] > 100, (base[0], panned[0]))
cam.set_look(None)
for _ in range(60):
    cam.update(1 / 60)
recentred = cam.to_screen(0, 0, 0)
check("free look springs back", abs(recentred[0] - base[0]) < 6, (base[0], recentred[0]))

# ------------------------------------------- other modes still work unchanged
from src.defense_world import DefenseWorld
from src.survival_world import SurvivalWorld
from src.versus_world import VersusWorld
from src.world import World
from src.entities import pvo

strike = World(drones.get("baba"), "Normal", seed=2)
check("strike mission still has 5 targets", len(strike.targets) == 5, len(strike.targets))
check("strike scenery still indestructible", all(b.max_hp == 0 for b in strike.buildings if not b.is_target))
for _ in range(120):
    strike.update(1 / 60, {"thrust": True, "fire": True})
check("strike mission runs", strike.result in ("playing", "won", "lost"), strike.result)

defense = DefenseWorld("aagun", "Normal", seed=4)
for _ in range(120):
    defense.update(1 / 60, {"left": True, "fire": True, "stick": (1.0, 0.0)})
check("defense mission runs with a stick", defense.result == "playing", defense.result)

survival = SurvivalWorld("Normal", seed=6)
start = pygame.Vector2(survival.player.pos)
for _ in range(120):
    survival.update(1 / 60, {"stick": (1.0, 0.0)})
check("survival moves on the stick", survival.player.pos.x > start.x + 20, survival.player.pos.x - start.x)

versus = VersusWorld(drones.get("fpv"), pvo.PVO_UNIT_TYPES[0], "Normal", 9, is_host=True, local_role="drone")
for _ in range(60):
    versus.host_update(1 / 60, {"stick": (0.0, 1.0), "thrust": True}, {"left": True})
check("versus match runs with a stick", versus.result == "playing", versus.result)

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("all checks passed")
