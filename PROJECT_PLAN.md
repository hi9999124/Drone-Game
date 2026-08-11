# Drone / PVO — Unity Project Plan

## 1. Project Overview

A 3D drone combat / air-defense (PVO) game built in Unity, playable from **both sides**:
offensive drone pilot and defensive PVO (air-defense) operator (turret/SAM gunner). Supports
offline play vs. AI bots (4 difficulty tiers), LAN and internet multiplayer with private
rooms/friends, and PCVR. Target platforms: **PC (Windows/Mac/Linux) + PCVR + mobile/tablet**.
Console is explicitly out of scope (see Constraints).

**Developer context:** total beginner to Unity, comfortable directing scope but will need
explanations alongside code, not just code. Budget is $0 — every tool/service chosen below
has a free tier sufficient for this project. Distribution via GitHub Releases (and optionally
itch.io) rather than paid storefronts.

## 2. Core Gameplay

- **Drone role:** pilot a physics-based drone (thrust/pitch/roll/yaw), FPV/third-person/top-down
  camera modes, weapons or evasion depending on mode.
- **PVO role:** control a ground-based turret/SAM emplacement — detect, track, and engage
  drones. Radar/detection cone, target lock, lead-prediction aiming.
- **Symmetry:** both roles share underlying "aim direction" and "hit detection" systems so
  drone-vs-drone and drone-vs-turret combat use the same core code paths.
- **Perspectives:** first-person (FPV cockpit / gunsight), third-person chase cam, and
  top-down/radar-style strategic view — swappable per player.
- **Modes:** offline vs. bots (Easy/Normal/Hard/Super Hard), LAN multiplayer, internet
  multiplayer via relay/lobby with private rooms, player limits, team limits.
- **VR:** PCVR support (Quest via Link/Air Link, or any PCVR headset) for the FPV drone
  cockpit and/or turret-gunner role, built on Unity XR Interaction Toolkit from day one so
  it isn't retrofitted later. Comfort options (snap-turn, vignette) required for the flight
  role due to motion-sickness risk.

## 3. Platform & Input

- Unity's **Input System** package (not the legacy Input Manager) — single unified input
  pipeline for keyboard/mouse, Xbox/PlayStation controllers (native USB/Bluetooth on PC),
  touch (mobile/tablet), and XR controllers.
- Design all control schemes as swappable "input maps" from the start rather than
  hard-coding one scheme and porting later.
- Steam Deck is treated as a PC target (controller + touch), not a separate platform.

## 4. Constraints & Decisions Already Made

- **No console builds.** Sony/Microsoft/Nintendo all require paid developer accounts,
  platform NDAs, and closed submission/cert processes — there is no free or GitHub-based
  sideload path, and Unity itself won't export a console build without a signed platform
  agreement. PC + controller is the deliberate substitute for "console feel."
  (Future option, not in current scope: Xbox ID@Xbox indie program, ~$19, if the project
  matures.)
- **$0 budget for all tooling and services** — every recommendation below must stay on a
  free tier.
- **Distribution:** GitHub Releases as primary channel; itch.io as a free secondary option
  worth setting up in parallel. Not distributing via Steam/console stores at this stage.

## 5. Tech Stack (all free tier)

| Concern | Tool | Notes |
|---|---|---|
| Engine | Unity LTS (2022 LTS or 2023 LTS) | Unity Personal license, free |
| Scripting | C#, Visual Studio Community or VS Code | |
| Input | Unity Input System package | KBM/controller/touch/XR unified |
| VR | Unity XR Interaction Toolkit + XR Device Simulator | Simulator allows testing without a working headset |
| Multiplayer netcode | Netcode for GameObjects (NGO) | Unity's official free netcode |
| Matchmaking/relay | Unity Relay + Unity Lobby | Free tier; gives room codes, player/team limits without self-hosted servers |
| LAN play | Same netcode, LAN discovery; Radmin VPN works transparently as it just presents as a LAN | |
| Friends/accounts backend | Cloudflare Workers + Cloudflare D1 (or KV) | Free tier; lightweight REST API for accounts, friend lists, invites |
| Version control / distribution | GitHub (repo + Releases) | Also consider itch.io for discoverability |
| Free art/audio (if needed) | Kenney.nl, itch.io CC0 packs, Sketchfab CC0, freesound.org | |

## 6. Phased Build Plan

### Phase 0 — Environment Setup
- Install Unity Hub → Unity LTS, install Visual Studio Community/VS Code with C# support
- Create Unity project; initialize GitHub repo (this becomes the version-control AND
  distribution channel)
- Install packages: Input System, XR Interaction Toolkit
- Set up basic folder structure: `/Scripts`, `/Prefabs`, `/Scenes`, `/Art`, `/Audio`

### Phase 1 — Drone Flight Controller (offline, single scene, foundation phase)
- Physics-based drone movement via Rigidbody (thrust, pitch/roll/yaw)
- Camera rig supporting FPV cockpit, third-person chase, top-down — swappable at runtime
- Build FPV cockpit camera mode in a VR-compatible way from the start (head-tracked,
  XR Interaction Toolkit conventions) even though initial testing will mostly be flat-screen
  or via XR Device Simulator
- Basic in-world/HUD readouts: altitude, speed, battery/fuel
- Input System wiring for KBM + controller (VR input wired but not yet fully tested live)
- **Milestone:** drone flies around an empty test world under player control

### Phase 2 — PVO / Air Defense Systems
- Turret/SAM prefab: rotation toward target, detection radius via sphere/cone raycasts or
  trigger volumes
- Shared weapon/hit-detection system usable by both drones and turrets (single source of
  truth for "fire" and "hit" logic)
- Radar/detection feed — this is where the top-down camera mode becomes functionally useful
  (not just cosmetic)
- Player-possessable turret role, aim-by-mouse (flat) and aim-by-head/hand (VR) sharing the
  same underlying "aim direction" abstraction
- **Milestone:** a player can possess either a drone or a turret in the same scene and
  they can engage each other

### Phase 3 — Bot AI & Complete Offline Mode
- State-machine AI (Patrol → Detect → Engage → Lost Target) for enemy drones and enemy
  turrets
- Difficulty tiers implemented as tunable parameters: reaction time, aim accuracy/spread,
  target-leading/prediction quality, fire rate — Easy/Normal/Hard/Super Hard
- Round structure, win/lose conditions
- **Milestone:** fully playable offline game, start to finish, against AI at any difficulty

### Phase 4 — Multiplayer
- Integrate Netcode for GameObjects
- Unity Relay + Lobby for internet play: room codes, player limits, team limits, public/private
  rooms
- Sync drone/turret transforms, firing, hit registration, scoring across clients
- LAN play validated (including over Radmin VPN or similar)
- VR and flat-screen clients coexist in the same match (netcode syncs position/rotation
  regardless of input method, so this should require no special-casing if Phase 1–2 were
  built cleanly)
- **Milestone:** two+ players can play a full match over LAN and over the internet via a
  room code

### Phase 5 — Friends, Accounts, Rooms Polish, Final Input Pass
- Lightweight accounts/friends backend on Cloudflare Workers + D1: register, add friend,
  accept/decline, see friend online status, invite-to-game, join-friend
- Invite/join-by-code flows built on top of Phase 4's Relay/Lobby system
- Full input polish pass across KBM, controller, touch, and real VR hardware (once headset
  is working) — remappable controls
- VR comfort settings: snap-turn vs. smooth turn, vignette, seated/standing calibration
- Package builds for GitHub Releases (and optionally itch.io)

## 7. Design Principles for Claude Code To Follow

- Keep drone and turret "aim/fire/hit" logic in shared, reusable systems rather than
  duplicating per-role — Phase 2 depends on this, and VR/flat-screen parity depends on it too.
- Build input and camera systems as swappable/data-driven from Phase 1 onward — retrofitting
  VR or a new control scheme later should not require rewriting core movement/aim code.
- Prioritize getting each phase to a genuinely playable milestone before adding the next
  phase's complexity — this is a beginner-friendly, incrementally-testable build order, not
  a "build everything then integrate" approach.
- Explain non-obvious Unity/C# concepts briefly when introducing them, since the developer
  is new to Unity specifically (general programming aptitude assumed, Unity-specific APIs
  are not).
- All chosen services/tools must remain free-tier; flag before introducing anything with a
  cost.

## 8. Explicitly Out of Scope (for now)

- Console builds/certification (PlayStation, Xbox, Switch)
- Paid backend services, paid Unity add-ons, or paid asset packs
- Full VR locomotion polish before Phase 5 (basic VR-compatible structure yes, full comfort
  pass no — deferred since headset is currently non-functional for live testing)
