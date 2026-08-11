# Drone / PVO

A simple 2D drone-flight game built with **Python + Pygame** — a real menu, a
pause screen, and an in-game HUD, no Unity or other engine required. See
[`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the design plan and what's next.

## Run it

Requires Python 3.9+.

```
pip install -r requirements.txt
python main.py
```

## Controls

| Key | Action |
|---|---|
| `W` / `Up Arrow` | Thrust forward |
| `A` / `Left Arrow` | Rotate left |
| `D` / `Right Arrow` | Rotate right |
| `Esc` | Pause / resume |

Flight is arcade-style: thrust always pushes in the direction you're currently
facing (like *Asteroids*), and the arena wraps at the edges.

## Project structure

```
main.py              Entry point
requirements.txt     Just pygame
src/
  game.py             Menu / Playing / Paused state machine and main loop
  drone.py            Player-controlled drone: physics, drawing
  constants.py         Screen size, color palette
  utils.py             Small color-lerp helper for UI hover animations
  ui/
    button.py           Hover-animated button widget
    menu.py              MainMenu and PauseMenu
    hud.py               In-game speed/throttle readout
    background.py        Grid background
```

## Status

Playable now: fly the drone around the arena from the main menu, pause mid-flight,
resume or return to the menu. Next up is a PVO turret to actually fight — see
[`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the plan.
