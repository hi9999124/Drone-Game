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
- [x] **Ram-hit fix + FPV Kamikaze rebalance**: ramming a target now only
      needs footprint overlap, not matching the building's exact altitude
      (see "Fixed bugs" below), and FPV Kamikaze one-shots a standard target
      instead of needing 3 airframes per building
- [x] **Accounts, coins, XP, levels, ranks, leaderboard**: optional sign-in
      (username/password, GitHub, or Google) syncing to a Cloudflare
      Worker + D1 backend (`backend/`); fully playable offline with none of
      this touched. See "Accounts & backend" below.
- [ ] iOS — see "Mobile & iOS" below; blocked on a decision, not on code
- [ ] **Online multiplayer (real-time PvP)** — not started; this is
      distinct from the accounts/leaderboard work above, which is
      turn-based (submit a score, read a leaderboard), not live netcode.
      See "Multiplayer" below for what real-time play actually costs
- [ ] Ground-based PVO/SAM turrets as a third entity type (the original
      "play the air-defence side" idea)
- [ ] Audio (engine loop, explosions) — no sound at all right now

## Fixed bugs (worth knowing if you touch this code again)

- **Ramming registered inconsistently / "can't hit any building."** Root
  cause: collision was gated on `player.altitude < building.height`. The
  drone spawns at a fixed altitude (110) with no gravity, so a player who
  never touches climb/descend sits at exactly that altitude forever, and
  building heights are chosen from `[55, 80, 110, 140, 175, 200]` — roughly
  half the city was physically unhittable no matter how precisely you flew
  into it. Fix (`World._resolve_player_collisions`): a kamikaze (ram-attack)
  drone hitting a *target* only needs XY footprint overlap now; general
  obstacle collision (non-target buildings, non-ram drones) still respects
  altitude, so flying safely over a short building still works.
- **FPV Kamikaze couldn't complete a mission.** Its `blast_damage` (120) was
  under half of a standard target's HP (260), and each airframe is a single
  use — destroying one target cost 3 airframes against a loadout of only 5
  total, making all 5 mission targets mathematically undestroyable with the
  starter drone. Bumped to 270 (one-shot). Both fixes verified with a
  scripted "fly straight at a shorter-than-spawn-altitude target and confirm
  it's destroyed" test, not just read through.

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
- `src/save_system.py` — profile + account + settings persistence
- `src/leveling.py` — XP/level/rank formula, mirrored exactly in
  `backend/src/levels.js`
- `src/backend.py` — HTTP client for the optional Cloudflare backend,
  including the GitHub/Google OAuth device-flow polling loops
- `src/ui/` — menus (incl. account sign-in, leaderboard), HUD, touch pads,
  text input, cached fonts
- `backend/` — Cloudflare Worker + D1: auth, coins/XP/levels, leaderboard
  (see "Accounts & backend" below)

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

## Accounts & backend

Cloudflare Worker + D1, `backend/` — see `backend/README.md` for the exact
deploy runbook (D1 database creation, GitHub/Google OAuth app registration,
`wrangler secret put` values). $0 on Cloudflare's free tier at this scale.

- **Auth**: username/password (PBKDF2-SHA256 via Web Crypto, no external
  dependency) or GitHub/Google via OAuth *device flow* -- the same pattern
  `gh auth login` uses: the desktop game shows a short code, opens the
  provider's approval page in the system browser, and polls until approved.
  No browser redirect back into the app is needed, which matters because a
  desktop app has no URL to redirect to. GitHub's device flow needs no
  client secret (public-client-friendly by design); Google's does, so for
  Google specifically the Worker proxies the whole flow and holds the secret
  server-side -- the desktop client never sees it.
- **Coins/XP/levels**: tracked locally regardless of account (`src/leveling.py`),
  mirrored exactly by `backend/src/levels.js` so a synced total never
  disagrees between the two. `xp = score`, `coins = score / 20` per mission.
- **Leaderboard**: `GET /leaderboard`, ranked by career (total) score.
- Every endpoint was verified against a real local D1 database
  (`wrangler dev`) end-to-end from `src/backend.py` -- signup, login, wrong
  password, score submission, leaderboard ranking, and the full sign-up ->
  play a mission -> score reaches the server -> appears on the leaderboard
  path -- not just written and assumed correct.
- **Not verified**: the actual GitHub/Google device-flow UX end-to-end,
  since that needs real registered OAuth apps and a real browser to click
  through, neither of which exists in this environment. The HTTP contracts
  match both providers' documented device-flow specs precisely, but this is
  the one piece worth testing by hand after deploying.

## Multiplayer (real-time PvP, not started)

Offline vs. AI is done, including difficulty tiers, and there's now an
optional online *leaderboard* (see "Accounts & backend" above) -- but that's
fundamentally different from live multiplayer: submitting a final score after
a match is a simple request/response, while two players seeing each other
move in real time is a standing connection with an authoritative simulation.
It's worth being clear about that gap before starting on it, since it isn't a
small feature so much as a change to how the whole game is structured.
Roughly what it involves:

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
