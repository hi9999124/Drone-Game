# Drone / PVO

A 3D drone combat / air-defense (PVO) game for Unity — playable as either the offensive
drone pilot or the defensive turret/SAM operator. Offline bots, LAN/internet multiplayer,
and PCVR support are all planned; see [`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the full
design doc and phased build order.

## Current status: Phase 0 + start of Phase 1

- [x] Repo structure, `.gitignore`, package manifest
- [x] Input System action map (`DroneControls.inputactions`) for keyboard/mouse + gamepad
- [x] Physics-based drone flight controller (`DroneController`, `DroneInputHandler`)
- [x] Swappable camera rig scaffold (`CameraRig`: first-person / third-person / top-down)
- [x] HUD readout scaffold (`DroneHUD`: altitude / speed / battery)
- [ ] Scene, prefab, and Inspector wiring (needs the Unity Editor GUI — see below)
- [ ] VR camera path validated in XR Device Simulator
- [ ] Phase 2 onward (turrets, AI, multiplayer)

## Getting started (Unity Editor setup)

This repo contains the C# scripts, Input Actions asset, and package manifest, but **no
`.unity` scene file or prefabs yet** — those are binary/YAML assets that Unity generates
and that only make sense to author inside the Editor GUI, which isn't available in this
environment. Here's how to pick it up locally:

1. **Install Unity Hub**, then install **Unity 2022 LTS** (any 2022.3.x patch) through it,
   including the **Android/iOS/PC build support** modules you want and the **Visual Studio**
   or **VS Code** C# integration if prompted.
2. **Clone this repo**, then in Unity Hub choose **Open → Add project from disk** and select
   the cloned folder. Unity will detect it's missing `ProjectSettings/` and initialize
   sensible defaults on first open (choose **3D (Built-in Render Pipeline)** if asked —
   this project intentionally stays off URP/HDRP for now to keep the beginner learning
   curve flat).
3. Unity will resolve the packages listed in `Packages/manifest.json` automatically
   (Input System, XR Interaction Toolkit, TextMeshPro, etc.) — this can take a few minutes
   on first open.
4. **Create the first scene**: `File → New Scene` (3D core template), save it as
   `Assets/Scenes/FlightTest.unity`.
5. **Build the test drone GameObject**:
   - Create an empty GameObject named `Drone`, add a `Rigidbody` component (uncheck
     "Use Gravity" is *not* needed — the controller's hover thrust cancels gravity itself).
   - Add the `DroneInputHandler` component, and drag `Assets/Input/DroneControls.inputactions`
     into its `Controls` field.
   - Add the `DroneController` component (it auto-requires the two above).
6. **Build the camera rig**: create three child `Camera` objects under `Drone` (or a
   separate `CameraRig` parent) named e.g. `FPVCamera`, `ThirdPersonCamera`, `TopDownCamera`,
   positioned/angled for each view. Add a `CameraRig` component (on the same object as
   `DroneInputHandler` or anywhere convenient), and drag the three cameras + the
   `DroneInputHandler` into its fields. Press **C** (or gamepad Y/Triangle) in Play mode to
   cycle views.
7. **Build the HUD**: `GameObject → UI → Canvas`, add three `TextMeshPro - Text` children
   for altitude/speed/battery, add a `DroneHUD` component and wire the `Drone` and the three
   text fields into it. (First time you add a TMP object, Unity will prompt to **Import TMP
   Essentials** — accept it.)
8. Press **Play**. WASD pitches/rolls, Q/E yaws, Space/Ctrl throttles up/down; a gamepad's
   left stick is throttle/yaw and right stick is pitch/roll (mirrors a real drone RC
   transmitter's "Mode 2" layout).

From here, Phase 1 continues with tuning flight feel and validating the FPV camera path in
the **XR Device Simulator** (Window → XR → XR Device Simulator window is added by the XR
Interaction Toolkit package) before moving on to Phase 2 (turrets/PVO).

## Project structure

```
Assets/
  Input/        Input System actions (DroneControls.inputactions)
  Scripts/
    Drone/       Flight controller + input handling
    Camera/      Swappable FPV/third-person/top-down camera rig
    UI/          HUD
    Core/        (reserved for Phase 2 shared aim/fire/hit-detection systems)
  Prefabs/       (empty — populated once the Drone GameObject above is prefabbed)
  Scenes/        (empty — see step 4 above)
  Art/, Audio/   (empty — free CC0 assets from Kenney.nl / Sketchfab / freesound.org as needed)
Packages/manifest.json   Unity package dependencies
PROJECT_PLAN.md          Full design doc and phased build plan
```

## Tech stack

See [`PROJECT_PLAN.md`](PROJECT_PLAN.md#5-tech-stack-all-free-tier) — everything used is
free tier: Unity Personal, Input System, XR Interaction Toolkit, Netcode for GameObjects,
Unity Relay/Lobby, and Cloudflare Workers/D1 for the later friends/accounts backend.
