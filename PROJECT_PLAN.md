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
- [x] **Release pipeline**: GitHub Actions builds Windows/macOS/Linux executables
      (PyInstaller) on every tag/dispatch, publishes to GitHub Releases under
      dev/alpha/beta/preview/stable channels
- [x] **Touch controls + Android APK**: on-screen thrust/rotate buttons
      (`src/ui/touch_controls.py`, multi-touch aware) and a Buildozer-based
      Android build in the same release pipeline
- [ ] iOS — see "Mobile & iOS" below; blocked on a decision, not on code
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

## Mobile & iOS

Android works with the same $0/GitHub-Releases model as desktop: Buildozer
packages the Pygame code into an unsigned debug `.apk`, and Android lets you
install any APK once you allow "unknown sources" — no store, no signing
account, no cost.

iOS cannot work the same way, and this isn't a tooling gap this project can
code its way around: **every app that runs on a real, non-jailbroken iPhone
must be cryptographically signed by a certificate Apple issued**, whether
it's installed via the App Store or sideloaded. The realistic free-tier
options, roughly in order of how much they resemble "download a file and
tap install":

- **AltStore / SideStore**: free, open-source sideloading tools. You (or
  each player) sign the app locally using your own free Apple ID. The catch:
  a free Apple ID's signature expires every 7 days, so AltServer/SideStore
  has to periodically re-sign the app (SideStore can do this over Wi-Fi in
  the background; AltStore's classic mode needs your computer on the same
  network occasionally). This is how free sideloaded emulators/apps
  typically distribute on iOS today.
- **Apple Developer Program ($99/year)**: lets you sign a build that installs
  normally and doesn't expire — either self-distributed (still needs a Mac +
  Xcode to build/sign) or through the App Store. This breaks the project's
  $0-budget constraint, so it's out of scope unless that constraint changes.
- Either path also needs a **Mac with Xcode** to produce the `.ipa` in the
  first place — GitHub Actions does have macOS runners that could do this in
  CI, but Pygame's iOS support is experimental/unreliable, unlike its
  well-trodden Android (python-for-android) and desktop paths. A more mature
  fallback would be porting the touch-control/rendering code to a framework
  with real iOS support (e.g. Kivy, which iOS-builds via `kivy-ios`), which
  is a meaningfully bigger job than the Android port was.

Net: Android is done. iOS is possible for $0 via AltStore/SideStore, but the
player experience (install a sideloading tool, sign with their own Apple ID,
periodic re-signing) is a real step down from "download and tap an APK" —
worth deciding on deliberately rather than defaulting into.

## Next step: Phase 2 — PVO / turret

- A turret entity that rotates toward the drone within a detection radius
- Shared "fire" and "hit" logic usable by both the drone and the turret, so
  drone-vs-turret combat doesn't duplicate collision code
- A loss condition (drone hit) and a way to see it in the interface (game-over screen)
