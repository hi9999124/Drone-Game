# Drone / PVO — 2D Project Plan

## Overview

A simple 2D drone combat/air-defense game, built with **Python + Pygame** — no game
engine, no external dependencies beyond `pygame` itself, runs as a desktop app on
Windows/Mac/Linux. This replaces an earlier, much larger Unity/3D/VR/multiplayer
concept: same core idea (pilot a drone, evade/engage air defenses), deliberately
scoped down to something a beginner can build, run, and extend without Unity.

Distribution stays $0: source + `requirements.txt` on GitHub, run via
`python main.py`. No paid services, no console/store submission.

## Status

- [x] **Menu → Flight → Pause state machine** with a real interface: title screen,
      hover-animated buttons, pause overlay
- [x] **Arcade 2D flight**: thrust-forward-and-turn drone physics (`src/drone.py`),
      screen-wrapping arena, engine glow effect tied to throttle
- [x] **HUD**: speed readout + throttle bar, semi-transparent panel over the game view
- [ ] PVO / turret entity — detection, aim, and a shared hit-detection system
- [ ] Win/lose condition, scoring
- [ ] Simple AI difficulty tiers (optional, once a turret exists to fight)

## Architecture

- `main.py` — entry point, creates and runs `Game`
- `src/game.py` — top-level state machine (`menu` / `playing` / `paused`) and the
  main loop (fixed-timestep-independent via delta time, so speed doesn't change
  with frame rate)
- `src/drone.py` — the player-controlled drone: position/velocity as `pygame.Vector2`,
  rotation, drag, speed cap
- `src/ui/` — `Button` (hover-animated), `MainMenu`, `PauseMenu`, `HUD`, background grid
- `src/constants.py` — screen size, color palette
- `src/utils.py` — small color-lerp helper used for hover animations

## Design principles

- Keep gameplay state (`Drone`, and later the turret) separate from UI/rendering
  state (`ui/`) so a future PVO entity or AI controller can drive the same `Drone`
  class without touching menu code.
- Everything driven by delta time (`dt`), never by frame count, so behavior is
  consistent across machines.
- No external assets required — everything is drawn with Pygame primitives
  (polygons, circles, rects) so the project runs from a fresh clone with just
  `pip install -r requirements.txt`.

## Next step: Phase 2 — PVO / turret

- A turret entity that rotates toward the drone within a detection radius
- Shared "fire" and "hit" logic usable by both the drone and the turret, so
  drone-vs-turret combat doesn't duplicate collision code
- A loss condition (drone hit) and a way to see it in the interface (game-over screen)
