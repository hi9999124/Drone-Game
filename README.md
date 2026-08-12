# Drone / PVO

A simple 2D drone-flight game built with **Python + Pygame** — a real menu, a
pause screen, and an in-game HUD, no Unity or other engine required. See
[`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the design plan and what's next.

## Play it

**No Python needed:** download a build from the [Releases page](../../releases).

- **Windows / macOS / Linux:** pick the matching `.zip`, extract it, and run
  `DronePVO` (or `DronePVO.exe` on Windows). Windows/macOS may warn that the
  app is from an unidentified developer since it isn't code-signed (that
  costs money — see `PROJECT_PLAN.md`'s $0-budget constraint); click through
  "Run anyway" / "Open anyway" to launch it.
- **Android:** download `DronePVO-android.apk`, open it on your phone, and
  allow "install from unknown sources" when prompted (it's not distributed
  through the Play Store, so Android warns by default — this is normal for
  any sideloaded APK). Use the on-screen buttons to fly.
- **iPhone/iOS:** not available yet. Apple requires every app to be signed
  before it can run on a real device, even sideloaded ones — there's no
  free, no-Mac way around that. See the note in `PROJECT_PLAN.md` for the
  realistic options.

**From source** (requires Python 3.9+):

```
pip install -r requirements.txt
python main.py
```

## Controls

| Key | Action |
|---|---|
| `W` / `Up Arrow` | Thrust forward |
| `S` / `Down Arrow` | Reverse thrust / brake |
| `A` / `Left Arrow` | Turn left |
| `D` / `Right Arrow` | Turn right |
| `Space` / `E` | Climb |
| `Shift` / `Q` | Descend |
| `F` / left click | Use airframe ability (bomb, rocket, boost) |
| `Esc` | Pause |
| `F11` | Toggle fullscreen (also in Settings; desktop only) |

Flight is arcade-style: thrust pushes in the direction you're facing (like
*Asteroids*), with a separate altitude axis on top.

On a touchscreen the same controls appear as on-screen pads — turn/thrust on
the left, altitude and FIRE on the right. They're mouse-clickable on desktop
too, and multi-touch aware, so you can hold thrust, turn and climb at once.

## The 2.5D world

The city is a flat top-down plane plus a real altitude axis. Altitude only ever
shifts a sprite *up the screen*, and every flying object drops a shadow on the
ground below it — that pairing is what reads as height. Buildings are drawn as
an extruded roof and front wall, and they physically block you: fly over a
120 m block or route around it, because clipping one at speed wrecks the
airframe.

## Game modes

**PLAY** from the main menu leads to a side-select screen with three
single-player modes, plus **MULTIPLAYER** for head-to-head play:

| Mode | You play | Objective |
|---|---|---|
| Drone Strike | A drone (see Airframes below) | Destroy every marked target while interceptors and PVO air defense hunt you |
| Air Defense | A PVO turret (flak gun or SAM site) | Shoot down waves of attacking drones before they destroy protected structures |
| Civilian Survival | A civilian on foot, unarmed | Reach shelter before each telegraphed strike lands; survive the bombardment |

Each is a genuinely different way of playing, not a reskin: flying-and-attacking,
aiming-and-shooting, and reading-the-map-and-reacting, respectively. See
[`PROJECT_PLAN.md`](PROJECT_PLAN.md) for what's next.

## Multiplayer

**MULTIPLAYER** from the main menu pits one human Drone Strike pilot against
one human PVO Defender, head to head, either over a local network / virtual
LAN, or over the internet through a room:

- Whoever hosts always flies the drone; whoever joins always mans the PVO
  defense — a fixed, simple pairing rather than a role-picker.
- The host's machine runs the only real simulation and streams state to the
  client every frame, so the two sides can never desync or disagree about
  who won.
- Drone wins by destroying every target (or the PVO turret); PVO wins by
  shooting down every one of the drone's airframes. Leaving mid-match counts
  as a forfeit for whoever left.

**LAN / RadminVPN** — no special setup for either: a virtual-LAN tool like
RadminVPN or Hamachi just makes a friend's PC look local, so it's the same
"join by address" flow either way.
- **Host**: pick your drone, then share the address shown (your LAN IP and
  a port).
- **Join**: pick your PVO unit, type the host's address, connect.

**Online Room** — play over the internet with a short room code, no network
setup on either side. Needs the optional backend (see "Accounts, coins,
levels, leaderboard" below) deployed with its Room relay.
- **Host a public room**: anyone can find and join it from the live browse
  list in Join Room.
- **Host a private room**: share the code with your friend yourself — it
  never shows up in the public list.
- **Join a room**: type a code, or click one straight out of the browse
  list.

## Airframes

| Airframe | Style | Ability | Unlocks at |
|---|---|---|---|
| FPV Kamikaze | Fast, fragile, 5 expendable airframes | Boost — ram the target | 0 |
| Baba Yaga | Heavy, tanky, slow | Drop Bomb — gravity-fed, needs altitude and lead | 500 |
| Shahed-256 | Very fast, barely steers | Terminal Dive — huge blast | 1500 |
| Hornet FPV | Reusable rocket platform | Fire Rocket — flat and fast | 3000 |

Unlocks are driven by *career* score, which accumulates across runs and is
saved automatically.

## Mission (Drone Strike)

Destroy every marked target block (red, with a crosshair on the roof) while
enemy FPV interceptors hunt you. Off-screen targets are marked by arrows at the
edge of the screen. Difficulty (Easy → Insane) changes interceptor count,
speed, reaction time, and whether they shoot back — same AI throughout, just
sharper numbers.

Targets are also guarded by ground-based **PVO air defense** — a ZU-23 flak
gun (rapid unguided fire, low-altitude only) and, from Hard difficulty up, a
Buk-style SAM site (long range, any altitude, fires a guided missile once
it's held a lock — watch the on-screen lock warning, you have that whole
window to break line of sight or outrun it). Destroying one is a bonus
objective (extra score), not required to win the mission.

## Saving

Progress and settings save automatically to `~/.dronepvo/savegame.json` (the
app's private directory on Android) after every mission and settings change.
Writes go through a temp file and atomic replace, so a crash mid-save can't
corrupt the profile.

## Accounts, coins, levels, leaderboard

Entirely optional — the game is fully playable offline with no account, and
coins/XP/levels are tracked locally either way. Signing in (from the main
menu's ACCOUNT screen) additionally syncs your progress to a small Cloudflare
backend and puts you on the online leaderboard.

- **Sign in** with a username/password, GitHub, or Google — pick whichever.
- **Coins & XP** are earned from mission score (`xp = score`,
  `coins = score / 20`); XP drives **levels**, and levels map to **ranks**
  (Rookie → Cadet → Veteran → Ace → Legend).
- **Leaderboard** ranks every signed-in player by career score.

The backend (Cloudflare Worker + D1) lives in [`backend/`](backend/) — see
[`backend/README.md`](backend/README.md) for exact deploy steps (it's not
live by default; the game points at a placeholder URL until you deploy one).
Once deployed, point *any* copy of the game at it — including an already-
downloaded `.exe`/APK, no rebuild needed — by editing
`backend_config.json` next to your save file (`~/.dronepvo/` on desktop);
the game creates this file with placeholder values the first time you run
it. Every backend endpoint was tested against a real local database before
being written up, not just designed on paper.

The same deployment also serves **Online Room** play (two Durable Objects,
`RoomRelay` + `RoomDirectory` — see `backend/src/room.js`) — no separate
setup, it comes with the Worker.

## Project structure

```
main.py               Entry point
requirements.txt      pygame + optional websockets (Online Room play only)
src/
  game.py              State machine (menu / mode select / settings / account / leaderboard / play / pause / result)
  world.py             Drone Strike: city generation, collisions, mission rules, depth-sorted draw
  defense_world.py     Air Defense: waves of raiders, protected structures, mission rules
  survival_world.py    Civilian Survival: telegraphed strikes, shelters, mission rules
  versus_world.py      Multiplayer: host-authoritative Drone vs. PVO simulation, snapshots
  net.py               LAN/RadminVPN transport: non-blocking UDP + JSON, no dependencies
  room_client.py       Online Room transport: WebSocket relay client, adapts to net.py's shape
  camera.py            Follow camera, screen shake, world -> screen projection
  drones.py            Airframe definitions (stats + abilities)
  save_system.py       Atomic JSON save/load for profile + account + settings
  leveling.py          XP/level/rank formula (mirrored exactly in backend/src/levels.js)
  backend.py           HTTP client for the optional Cloudflare backend + OAuth device flows
  constants.py         Screen size, projection scale, palette
  utils.py             lerp / clamp helpers
  entities/
    base.py             Shared flight integration + ground-shadow drawing
    player.py           Player drone, ability handling
    enemy.py            Interceptor AI + difficulty profiles
    building.py         Apartment blocks: extruded 2.5D draw, damage
    projectile.py       Bombs, rockets, guided missiles, explosions
    pvo.py              Ground-based air defense: flak gun + SAM site stats/AI
    player_turret.py    Air Defense: player-controlled turret (aim + fire)
    raider.py           Air Defense: attacking-drone AI
    civilian.py         Civilian Survival: player character (on-foot movement)
  ui/
    button.py           Hover-animated button + settings option row
    menu.py             Main / drone select / settings / account / leaderboard / multiplayer / pause / result screens
    hud.py               Flight, ability and mission panels, off-screen target arrows
    touch_controls.py   Responsive on-screen pads (touch + mouse)
    text_input.py        Single-line text field (username/password entry)
    fonts.py             Cached font loader
buildozer.spec        Android (APK) packaging config for python-for-android
backend/               Cloudflare Worker + D1 + Durable Objects: accounts, coins/XP/levels,
                        leaderboard, Online Room relay (see backend/README.md)
  src/room.js           RoomRelay + RoomDirectory Durable Objects: WebSocket pairing/relay,
                        public room browse list
```

## Release channels

Releases are cut by pushing a tag matching `v<version>[-<channel>.<n>]`; a
GitHub Actions workflow (`.github/workflows/release.yml`) then builds a
PyInstaller executable for Windows/macOS/Linux plus an Android APK (via
Buildozer/python-for-android) and publishes them to the
[Releases page](../../releases) automatically. The Android build is
best-effort: if it fails, the desktop builds still publish (see
`continue-on-error` in the workflow).

| Channel | Tag example | Meaning |
|---|---|---|
| Dev | `v0.1.0-dev.1` | Frequent, possibly-broken snapshots |
| Alpha | `v0.1.0-alpha.1` | Early, functional but incomplete |
| Beta | `v0.1.0-beta.1` | Feature-complete, still being tuned |
| Preview | `v0.1.0-preview.1` | Release candidate |
| Stable | `v0.1.0` | No `-channel` suffix |

The channel is shown in the release title (e.g. "Alpha v0.2.0-alpha.4"), but
none of them are marked as a GitHub "pre-release" — GitHub's platform rule is
that a prerelease can *never* become the repo's "Latest" release, no matter
what, so marking them that way meant the newest build was permanently
excluded from the "Latest" badge and the repo page fell back to a bare
"N tags" widget. Whichever release is newest becomes "Latest" regardless of
channel.

## Status

Playable end to end: pick an airframe, fly a strike mission over a 2.5D city
against interceptors at four difficulty tiers, win or lose, and keep your
career progress. **Online multiplayer is not implemented yet** — everything
today is offline vs. AI. See [`PROJECT_PLAN.md`](PROJECT_PLAN.md) for what's
next.
