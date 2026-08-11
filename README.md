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
| `A` / `Left Arrow` | Rotate left |
| `D` / `Right Arrow` | Rotate right |
| `Esc` | Pause / resume |

Flight is arcade-style: thrust always pushes in the direction you're currently
facing (like *Asteroids*), and the arena wraps at the edges.

On Android (or any touchscreen), three on-screen buttons in the bottom corners
do the same job: `<` `>` to rotate, `^` to thrust. They're mouse-clickable on
desktop too, and support holding two at once (e.g. thrust + turn).

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
    touch_controls.py    On-screen thrust/rotate buttons (touch + mouse)
buildozer.spec        Android (APK) packaging config for python-for-android
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

Dev/Alpha/Beta/Preview are all marked as GitHub "pre-releases"; only a plain
`vX.Y.Z` tag is marked as the latest stable release.

## Status

Playable now: fly the drone around the arena from the main menu, pause mid-flight,
resume or return to the menu. Next up is a PVO turret to actually fight — see
[`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the plan.
