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
- [x] **Ground-based PVO air defense**: two unit types (`src/entities/pvo.py`)
      guarding mission targets -- ZU-23 flak (short range, low-altitude
      only, rapid unguided fire) and a Buk-style SAM site (long range, any
      altitude, guided homing missile after a visible lock-on window). AI-
      controlled hazard in the existing single-player mission for now; the
      same `PVOTurret`/`PVOUnitType` system is the foundation the *playable*
      PVO Defenders faction (see "Teams & multiplayer" below) builds on.
- [x] **Playable PVO Defenders (Air Defense mode)**: choose your side from
      the main menu. Man a flak gun or SAM site (`src/entities/player_turret.py`)
      defending civilian structures (`Building.is_protected`) from waves of
      attacking BPLAs (`src/entities/raider.py`), mission rules in
      `src/defense_world.py`. Single-player against AI raiders for now;
      networking this against a human Drone player is Stage 3 below.
- [x] **Playable Civilians (Survival mode)**: also from the main menu's mode
      select. On foot, no weapon, direct 8-way movement -- deliberately a
      different verb from the other two modes (flying-and-attacking,
      aiming-and-shooting). Telegraphed strikes (a warning circle, then
      impact) land across the city; reach a marked shelter
      (`Building.is_shelter`) before the timer runs out or take damage.
      Mission rules in `src/survival_world.py`.
- [x] **Free Flight (destruction sandbox)** — `src/sandbox_world.py`. The
      first entry on the mode-select screen and the one the phone build is
      shaped around: the entire city is destructible (`Building.make_destructible`
      gives every block HP scaled by its height), the streets are stocked with
      explosive props (`src/entities/prop.py` — fuel depots, tankers, cars,
      comms masts, with fuel chaining up to 3 links deep), nothing hostile
      spawns, airframes are unlimited and ordnance trickles back on a timer.
      No win, no loss, no timer: leaving via pause ends the run and shows a
      session summary. Deliberately pays **no** coins/XP/career score and
      never submits to the leaderboard — the run is unbounded and the city is
      defenceless, so any reward would be farmable and would devalue every
      ranked number next to it.
- [x] **One-thumb touch controls** — a floating analog joystick (left half of
      the screen; the drone banks toward wherever you push and throttles by
      how far — `PlayerDrone._apply_stick`) plus a camera pad (right half;
      pans the view off the drone and springs back — `Camera.set_look`),
      altitude/FIRE buttons, and an on-screen pause button, since a phone has
      no ESC key. The old six-button pads are still there under Settings →
      Touch layout. The stick feeds Air Defense's turret and Survival's
      civilian too, not just the drone.
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

## Checks

There's no test framework in the project (and no CI job running one yet), but
two headless scripts drive the real game loop end to end and are the thing to
run before pushing gameplay changes:

```
python tests/smoke_sandbox.py   # Free Flight rules, props/chaining, stick steering, camera pan,
                                # plus "every other mode still behaves" regressions
python tests/smoke_game.py      # the real Game state machine: menu -> mode select -> play ->
                                # pause -> result, at desktop and phone resolutions
```

Both run under SDL's dummy video driver, so they work over SSH/CI with no
display, and both exit non-zero on the first failed check.

## Architecture

- `main.py` — entry point, creates and runs `Game`
- `src/game.py` — state machine (`menu` / `drone_select` / `settings` /
  `playing` / `paused` / `result`) and the main loop, delta-time driven so
  behaviour doesn't change with frame rate
- `src/world.py` — owns the city, everything flying in it, collision resolution
  and the win/lose rules
- `src/sandbox_world.py` — Free Flight: subclasses `World` and replaces exactly
  the mission rules a sandbox doesn't have (no hostiles, no targets, no
  win/lose, free respawns, self-reloading ordnance), plus prop damage and the
  fuel-chain reaction
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

## Teams & multiplayer (the full vision, staged)

The goal: three playable sides -- **Drones** (existing), **PVO Defenders**
(ground-based air defense, `src/entities/pvo.py`), and **Civilians**
(survive/protect the population under attack) -- playable against each other
over LAN, RadminVPN, or a real room server with public/private lobbies. This
is genuinely several separate large pieces of work, not one feature, and
they have a real dependency order: you can't network a faction that doesn't
exist yet, and you can't build rooms/matchmaking on top of a simulation that
isn't authoritative. Building it out of order means rewriting whatever came
first.

**Stage 1 -- PVO Defenders content (done).**
`PVOTurret`/`PVOUnitType` (flak + SAM, radar detection, lock-on warning,
homing missiles) exist as AI hazards in the Drone Strike mission, and the
same weapon stats now drive a fully playable **Air Defense mode** -- pick a
side from the main menu, man a turret, defend civilian structures from wave
after wave of attacking BPLAs. This proved the faction is fun and balanced
*before* any networking touches it (verified via scripted-pilot headless
testing across every difficulty, same as every other balance pass this
project has had), and is exactly what a networked human PVO player will be
controlling once Stage 3 exists. Remaining, lower-priority polish: more unit
types (a radar station buffing nearby SAM range, a mobile short-range SAM).

**Stage 2 -- Civilians (survival) mode (done).**
`src/survival_world.py`: on foot, no weapon, reach a marked shelter before a
telegraphed strike lands. Its own win/lose rules (survive the bombardment
duration vs. HP hitting zero), not a reskin of Drone Strike or Air Defense --
verified via headless testing that both a "run to shelter" and a "don't
react to warnings" scripted player can complete it, and that a forced
direct hit both damages the player and can end the mission in a loss.

**Stage 3 -- LAN direct-connect multiplayer (done).**
`src/net.py` (non-blocking UDP + JSON, zero dependencies) and
`src/versus_world.py` (host-authoritative Drone vs. PVO simulation: the host
runs the only real physics and streams state snapshots; the client only ever
applies them, never simulates -- eliminates desync by construction rather
than reconciling it). Fixed roles keep the UI simple: whoever hosts plays
Drone Strike, whoever joins plays PVO Defense. Both sides build the identical
static city from a shared seed, so only dynamic state crosses the wire.
RadminVPN/Hamachi need no special integration at all -- they just make a
remote IP look local, so "LAN play" and "play over RadminVPN" are the exact
same Host/Join-by-address code path in `src/ui/menu.py`'s new multiplayer
screens. Verified with two real separate OS processes exchanging real UDP
packets over loopback (join/start handshake, streaming state snapshots,
forfeit-on-leave), and with two real, fully wired `Game` instances completing
a match end to end -- not just the in-process simulation logic.

**Stage 4 -- Room server (public + private rooms) (done).**
The existing Cloudflare Worker (`backend/`), extended with two Durable
Objects (`backend/src/room.js`): `RoomRelay` (one instance per room code,
pairs exactly two WebSocket peers and forwards every message verbatim --
deliberately dumb, since the actual match protocol is the exact same
{"type": "join"/"start"/"input"/"state"/"leave", ...} messages Stage 3
already speaks over UDP) and `RoomDirectory` (a single persistent instance
tracking which room codes are currently public, for the browse list; stale
entries -- e.g. a host that crashed without a clean disconnect -- prune
themselves after 5 minutes). `src/room_client.py` adapts a WebSocket
connection to the exact same (addr, message) send()/poll() shape
`net.UDPTransport` uses, so none of Stage 3's host/join/update/result logic
in `game.py` needed to change -- only *getting* two players onto that shared
transport differs (connect to the relay, then create_room-or-join_room, vs.
a direct UDP packet). Needs the optional `websockets` package (guarded
import, LAN play still needs nothing beyond it); private rooms never appear
in the directory, so joining one always requires already knowing the code.
Verified against a real `wrangler dev` relay: public room announce/list/
prune, private rooms staying hidden, join-nonexistent and room-full error
paths, and two full `Game` instances completing a match both by typed code
and by clicking a room out of the live public browser. This work also
surfaced and fixed a latent crash in Stage 3's LAN join screen (polling a
transport that didn't exist yet if a frame rendered before CONNECT was
pressed) -- caught by testing the Room join screen the same way and ported
back.

Building 3 and 4 before 1 and 2 exist would mean networking two factions
that don't have gameplay yet, and rewriting the connection model once rooms
need to broker something more complex than "one host, one client."

## Other next steps

- **Audio** — engine loop, explosions, target-destroyed sting. Free CC0 sources
  are listed in the tech-stack notes; nothing here costs money.
- **More airframes** — `src/drones.py` is a plain table; adding one is a single
  `DroneType(...)` entry plus an unlock threshold.
