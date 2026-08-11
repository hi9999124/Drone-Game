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
- [x] **Touch controls + Android APK**: responsive on-screen pads
      (`src/ui/touch_controls.py`, multi-touch aware) and a Buildozer-based
      Android build in the same release pipeline
- [x] **2.5D world**: altitude axis with ground shadows and extruded buildings
      (`src/camera.py` projection, `src/entities/building.py`)
- [x] **Airframe selection** with four drones, distinct stats and abilities,
      score-gated unlocks (`src/drones.py`, `DroneSelectMenu`)
- [x] **Save / autosave / settings**: atomic JSON profile + settings
      (`src/save_system.py`), settings menu with working difficulty, FPS,
      screen-shake and touch-control options
- [x] **Structures + enemies**: procedural abandoned apartment blocks, mission
      targets, enemy FPV interceptors with a patrol/chase/attack state machine
      and four difficulty tiers
- [x] **Full mission loop**: win/lose conditions, scoring, result screen,
      career progression
- [ ] iOS — see "Mobile & iOS" below; blocked on a decision, not on code
- [ ] **Online multiplayer** — not started. Everything today is offline vs. AI;
      see "Multiplayer" below for what this actually costs
- [ ] Ground-based PVO/SAM turrets as a third entity type (the original
      "play the air-defence side" idea)
- [ ] Audio (engine loop, explosions) — no sound at all right now

## Architecture

- `main.py` — entry point, creates and runs `Game`
- `src/game.py` — state machine (`menu` / `drone_select` / `settings` /
  `playing` / `paused` / `result`) and the main loop, delta-time driven so
  behaviour doesn't change with frame rate
- `src/world.py` — owns the city, everything flying in it, collision resolution
  and the win/lose rules
- `src/camera.py` — follow camera, screen shake, and the world→screen
  projection that creates the 2.5D look
- `src/entities/` — `base.Aircraft` (shared flight integration + shadows),
  `player`, `enemy`, `building`, `projectile`
- `src/drones.py` — airframe stat/ability table, the single place to tune or
  add a drone
- `src/save_system.py` — profile + settings persistence
- `src/ui/` — menus, HUD, touch pads, cached fonts

### How the 2.5D projection works

The world is a flat XY plane with an altitude (Z) axis bolted on. The entire
trick lives in `Camera.to_screen()`:

```
screen_x = world_x - cam_x + WIDTH/2
screen_y = world_y - cam_y + HEIGHT/2 - altitude * Z_SCALE
```

Altitude only shifts things up the screen; it never changes X. Two consequences
make it read as 3D without any 3D maths:

1. Every flyer draws a **ground shadow** at its own XY with altitude 0. The gap
   between sprite and shadow *is* the perceived height.
2. Vertical side walls project to zero screen width, so a building only ever
   needs its **roof quad and front wall** drawn — which is why the buildings
   are cheap despite looking solid.

Everything is then **depth-sorted by world Y** (painter's algorithm) so nearer
objects overlap farther ones.

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

## Multiplayer (not started)

Offline vs. AI is done, including difficulty tiers. Online is the one item from
the request that is **not** built, and it's worth being clear about why before
starting it: it isn't a feature so much as a change to how the whole game is
structured. Roughly what it involves:

- **Authority.** Right now `World` mutates state directly and trusts itself.
  Networked play needs one authoritative simulation (host or dedicated server)
  with clients sending *inputs* rather than positions, or every player can
  simply declare they won.
- **Serialization + tick sync.** Entity state has to become something
  serialisable and reconcilable, with interpolation for remote entities, or
  everything jitters.
- **Transport.** Python has no batteries-included game netcode. LAN is
  tractable with raw UDP sockets; internet play needs either port forwarding
  (bad UX) or a relay server (a hosting cost, which the $0 constraint rules
  out — unless a free tier like Cloudflare Workers can be made to fit, which
  is worth investigating before committing).

A sensible order: **LAN two-player first** (no relay, no accounts, proves the
authority model), and only then look at internet play. Trying to do rooms,
accounts and matchmaking before the simulation is authoritative would mean
rewriting all of it.

## Other next steps

- **Ground PVO/SAM turrets** — the original "play the air-defence side" idea.
  The `Aircraft` base and the shared detonate/damage path in `World` already
  give this most of what it needs.
- **Audio** — engine loop, explosions, target-destroyed sting. Free CC0 sources
  are listed in the tech-stack notes; nothing here costs money.
- **More airframes** — `src/drones.py` is a plain table; adding one is a single
  `DroneType(...)` entry plus an unlock threshold.
