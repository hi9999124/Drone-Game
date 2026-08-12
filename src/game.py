import os
import sys

import pygame

from . import backend, constants, drones, leveling, save_system, world as world_module
from .camera import Camera
from .defense_world import DefenseWorld
from .survival_world import SurvivalWorld
from .ui.hud import HUD
from .ui.menu import (
    AccountMenu,
    DefenseSelectMenu,
    DroneSelectMenu,
    HowToMenu,
    LeaderboardMenu,
    MainMenu,
    ModeSelectMenu,
    PauseMenu,
    ResultMenu,
    SettingsMenu,
)
from .ui.touch_controls import TouchControls

STATE_MENU = "menu"
STATE_MODE_SELECT = "mode_select"
STATE_DRONE_SELECT = "drone_select"
STATE_DEFENSE_SELECT = "defense_select"
STATE_SETTINGS = "settings"
STATE_ACCOUNT = "account"
STATE_LEADERBOARD = "leaderboard"
STATE_HOWTO = "howto"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_RESULT = "result"

# python-for-android sets this env var; it's the standard way to detect
# "running as a packaged Android app" from within the app itself.
IS_ANDROID = "ANDROID_ARGUMENT" in os.environ
IS_WINDOWS = sys.platform == "win32"


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Drone / PVO")

        self.data = save_system.load()
        self.profile = self.data["profile"]
        self.account = self.data["account"]
        self.settings = self.data["settings"]
        self.pending_score_submit = None

        self.screen = None
        if IS_ANDROID:
            # Phones vary in resolution, so take a fullscreen surface at native
            # size and update the shared constants before any UI lays itself out.
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            constants.WIDTH, constants.HEIGHT = self.screen.get_size()
        else:
            self._apply_display_mode()

        self.clock = pygame.time.Clock()
        self.running = True

        self.camera = Camera()
        self.hud = HUD()
        self.touch = TouchControls()
        self.world = None
        self.state = STATE_MENU
        self.previous_state = STATE_MENU
        self._tracked_player = None

        self._build_menus()

    # ------------------------------------------------------------------ setup

    def _build_menus(self):
        self.main_menu = MainMenu(
            self.profile,
            self.account,
            self._open_mode_select,
            self._open_howto,
            self._open_account,
            self._open_leaderboard,
            self._open_settings,
            self._quit,
        )
        self.mode_select_menu = ModeSelectMenu(
            self._open_drone_select, self._open_defense_select, self._start_survival_mission, self._close_mode_select
        )
        self.howto_menu = HowToMenu(self._close_howto)
        self.pause_menu = PauseMenu(
            self._resume,
            self._open_loadout_select,
            self._open_settings,
            self._open_howto,
            self._return_to_menu,
            self._quit,
        )
        self.settings_menu = SettingsMenu(
            self.settings, self._close_settings, self._on_settings_changed, show_fullscreen_option=not IS_ANDROID
        )
        self.drone_menu = None
        self.defense_menu = None
        self.result_menu = None
        self.account_menu = None
        self.leaderboard_menu = None

    @property
    def show_touch(self):
        mode = self.settings.get("touch_controls", "Auto")
        if mode == "On":
            return True
        if mode == "Off":
            return False
        return IS_ANDROID

    # ------------------------------------------------------------- state flow

    def _open_mode_select(self):
        self.previous_state = self.state
        self.state = STATE_MODE_SELECT

    def _close_mode_select(self):
        self.state = STATE_PAUSED if self.previous_state == STATE_PAUSED else STATE_MENU

    def _open_drone_select(self):
        self.drone_menu = DroneSelectMenu(
            self.profile,
            self._start_mission,
            self._close_drone_select,
            selected_key=self.profile.get("last_drone"),
        )
        self.previous_state = self.state
        self.state = STATE_DRONE_SELECT

    def _close_drone_select(self):
        # Back out to wherever we came from: mode select, a paused mission,
        # or (only reachable via a stale/legacy path) the main menu directly.
        self.state = self.previous_state if self.previous_state in (STATE_PAUSED, STATE_MODE_SELECT) else STATE_MENU

    def _open_defense_select(self):
        self.defense_menu = DefenseSelectMenu(self._start_defense_mission, self._close_defense_select)
        self.previous_state = self.state
        self.state = STATE_DEFENSE_SELECT

    def _close_defense_select(self):
        self.state = self.previous_state if self.previous_state in (STATE_PAUSED, STATE_MODE_SELECT) else STATE_MENU

    def _open_loadout_select(self):
        # PauseMenu's single "CHANGE LOADOUT" button dispatches to whichever
        # select screen matches the mission already in progress -- there's
        # no reason to make a player re-choose attack-vs-defend mid-mission.
        # Survival has no loadout to pick (just the one character), so it
        # falls back to mode select -- effectively "change side" for it.
        mode = self.world.mode if self.world is not None else "strike"
        if mode == "defense":
            self._open_defense_select()
        elif mode == "survival":
            self._open_mode_select()
        else:
            self._open_drone_select()

    def _open_howto(self):
        self.previous_state = self.state
        self.state = STATE_HOWTO

    def _close_howto(self):
        self.state = STATE_PAUSED if self.previous_state == STATE_PAUSED else STATE_MENU

    def _open_settings(self):
        self.previous_state = self.state
        self.state = STATE_SETTINGS

    def _close_settings(self):
        self.state = STATE_PAUSED if self.previous_state == STATE_PAUSED else STATE_MENU

    def _on_settings_changed(self, key=None):
        self.camera.enable_shake = self.settings.get("screen_shake", True)
        if key == "fullscreen" and not IS_ANDROID:
            self._apply_display_mode()
            self._reflow_for_resolution()
        self._autosave()

    def _apply_display_mode(self):
        if IS_WINDOWS:
            self._apply_display_mode_windows()
            return

        # Genuinely change resolution (like the Android branch above always
        # has) rather than stretching a fixed 1280x720 buffer to fit --
        # SCALED was tried first and made fullscreen look blurry/pixelated
        # since it's still only ever rendering at the windowed resolution.
        # constants.WIDTH/HEIGHT get overwritten to match, and every menu's
        # cached layout is rebuilt below so it's sharp at the real size.
        #
        # (0, 0) + FULLSCREEN is the pygame/SDL idiom for "cover the desktop
        # at its current mode" (SDL_WINDOW_FULLSCREEN_DESKTOP) -- the same
        # call the Android branch above already uses with no issues.
        fullscreen = self.settings.get("fullscreen", False)
        try:
            if fullscreen:
                self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            else:
                self.screen = pygame.display.set_mode((constants.WINDOWED_WIDTH, constants.WINDOWED_HEIGHT))
        except pygame.error:
            # No usable display (e.g. SDL's "dummy" video driver, used for
            # headless testing) -- fall back rather than crashing. Only ever
            # happens off a real display anyway.
            self.settings["fullscreen"] = False
            self.screen = pygame.display.set_mode((constants.WINDOWED_WIDTH, constants.WINDOWED_HEIGHT))

        constants.WIDTH, constants.HEIGHT = self.screen.get_size()

    def _apply_display_mode_windows(self):
        """Windows gets a fundamentally different mechanism: a normal,
        resizable window whose "fullscreen" is just the OS's own maximize --
        the literal same ShowWindow(SW_MAXIMIZE) call behind every other
        app's maximize button (and Win+Up / double-clicking the title bar).
        Three earlier attempts at doing this through SDL's own fullscreen
        display modes each broke in a different Windows-specific way (a real
        display mode switch disrupting every other app's fullscreen state, a
        hand-rolled borderless window positioning itself incorrectly, DPI
        virtualization cutting the window down to one corner) -- asking
        Windows to do exactly what it already does for every other window
        sidesteps all of that, since it can't behave differently for us than
        it does for "other apps" queried directly.

        The window itself is only ever created once; toggling fullscreen
        after that is just maximize/restore on the existing window rather
        than recreating it (recreating was part of what made earlier
        attempts fragile). The resulting resize arrives as a VIDEORESIZE
        event on a later frame (see _handle_events), which is what actually
        updates constants.WIDTH/HEIGHT and reflows menus/touch layout --
        ShowWindow doesn't resize anything synchronously from Python's side,
        and this same event path also picks up the player manually
        dragging/snapping/maximizing the window themselves.
        """
        try:
            if self.screen is None:
                self.screen = pygame.display.set_mode(
                    (constants.WINDOWED_WIDTH, constants.WINDOWED_HEIGHT), pygame.RESIZABLE
                )
                constants.WIDTH, constants.HEIGHT = self.screen.get_size()

            import ctypes

            hwnd = pygame.display.get_wm_info()["window"]
            sw_maximize, sw_restore = 3, 9
            ctypes.windll.user32.ShowWindow(hwnd, sw_maximize if self.settings.get("fullscreen", False) else sw_restore)
        except (pygame.error, OSError, KeyError, AttributeError):
            # No usable display/window handle (e.g. SDL's "dummy" video
            # driver used for headless testing) -- fall back to a plain
            # windowed surface rather than crashing.
            self.settings["fullscreen"] = False
            if self.screen is None:
                self.screen = pygame.display.set_mode((constants.WINDOWED_WIDTH, constants.WINDOWED_HEIGHT))
                constants.WIDTH, constants.HEIGHT = self.screen.get_size()

    def _reflow_for_resolution(self):
        """Rebuilds everything whose layout was cached off constants.WIDTH/
        HEIGHT at construction time, so a resolution change actually takes
        effect instead of leaving menus/touch pads positioned for whatever
        size was active when the game started."""
        self._build_menus()
        self.touch.layout()

    def _toggle_fullscreen(self):
        self.settings["fullscreen"] = not self.settings.get("fullscreen", False)
        self._apply_display_mode()
        self._reflow_for_resolution()
        self._autosave()

    def _open_account(self):
        # Signing in deliberately does NOT auto-navigate away: the screen
        # shows a "signed in as ..." confirmation in place, and the player
        # leaves via BACK whenever they're ready. on_signed_in is a hook for
        # anything else that might care later; nothing needs it today.
        self.account_menu = AccountMenu(self.data, self._close_account, lambda: None, self._autosave)
        self.previous_state = self.state
        self.state = STATE_ACCOUNT

    def _close_account(self):
        self.state = STATE_PAUSED if self.previous_state == STATE_PAUSED else STATE_MENU

    def _open_leaderboard(self):
        self.leaderboard_menu = LeaderboardMenu(self._close_leaderboard)
        self.previous_state = self.state
        self.state = STATE_LEADERBOARD

    def _close_leaderboard(self):
        self.state = STATE_PAUSED if self.previous_state == STATE_PAUSED else STATE_MENU

    def _start_mission(self, drone_key):
        drone_type = drones.get(drone_key)
        self.profile["last_drone"] = drone_key
        self._autosave()

        self.world = world_module.World(drone_type, self.settings.get("difficulty", "Normal"))
        # The single highest-impact thing a new player doesn't know: flying
        # at spawn altitude clips buildings up to 200m tall constantly.
        # Repeated in the moment it matters, not just buried in HOW TO PLAY.
        self.world.notify("Climb above 200m to fly over buildings safely", duration=5.0)
        self.camera.enable_shake = self.settings.get("screen_shake", True)
        self.camera.snap_to(self.world.player.pos)
        self._tracked_player = self.world.player
        self.touch.release_all()
        self.state = STATE_PLAYING

    def _start_defense_mission(self, unit_key):
        self.world = DefenseWorld(unit_key, self.settings.get("difficulty", "Normal"))
        self.world.notify("Defend the marked structures from incoming raiders", duration=5.0)
        self.camera.enable_shake = self.settings.get("screen_shake", True)
        self.camera.snap_to(self.world.player.pos)
        self._tracked_player = self.world.player
        self.touch.release_all()
        self.state = STATE_PLAYING

    def _start_survival_mission(self):
        self.world = SurvivalWorld(self.settings.get("difficulty", "Normal"))
        self.world.notify("No weapon -- reach a shelter before the warning circle detonates", duration=5.0)
        self.camera.enable_shake = self.settings.get("screen_shake", True)
        self.camera.snap_to(self.world.player.pos)
        self._tracked_player = self.world.player
        self.touch.release_all()
        self.state = STATE_PLAYING

    def _retry(self):
        if self.world is None:
            self._start_mission(self.profile.get("last_drone", "fpv"))
        elif self.world.mode == "defense":
            self._start_defense_mission(self.world.player.type.key)
        elif self.world.mode == "survival":
            self._start_survival_mission()
        else:
            self._start_mission(self.profile.get("last_drone", "fpv"))

    def _resume(self):
        self.touch.release_all()
        self.state = STATE_PLAYING

    def _return_to_menu(self):
        self.world = None
        self.state = STATE_MENU

    def _quit(self):
        self._autosave()
        self.running = False

    def _autosave(self):
        save_system.save(self.data)

    def _poll_score_submit(self):
        """Checks a backend.submit_score() call started in _finish_mission.

        Fire-and-forget: the local profile already applied the same reward
        formula (mirrored exactly in backend/src/levels.js) the instant the
        mission ended, so the result screen never waits on the network. This
        just adopts the server's numbers as the final word once they arrive,
        in case of drift (e.g. a second device also played meanwhile) -- and
        silently drops the result if the request failed, since local
        progress this session is never lost either way.
        """
        pending = self.pending_score_submit
        if pending is None or not pending.done:
            return
        self.pending_score_submit = None
        if pending.error or pending.value is None:
            return
        profile = pending.value.get("profile")
        if not profile:
            return
        self.profile["coins"] = profile["coins"]
        self.profile["xp"] = profile["xp"]
        self.profile["level"] = profile["level"]
        self.profile["best_score"] = max(self.profile["best_score"], profile["best_score"])
        self._autosave()

    # ------------------------------------------------------------- main loop

    def run(self):
        while self.running:
            dt = min(self.clock.tick(constants.FPS) / 1000.0, 0.05)
            self._handle_events(dt)
            self._update(dt)
            self._draw()
        self._autosave()
        pygame.quit()
        sys.exit()

    def _active_menu(self):
        if self.state == STATE_MENU:
            return self.main_menu
        if self.state == STATE_MODE_SELECT:
            return self.mode_select_menu
        if self.state == STATE_DRONE_SELECT:
            return self.drone_menu
        if self.state == STATE_DEFENSE_SELECT:
            return self.defense_menu
        if self.state == STATE_SETTINGS:
            return self.settings_menu
        if self.state == STATE_ACCOUNT:
            return self.account_menu
        if self.state == STATE_LEADERBOARD:
            return self.leaderboard_menu
        if self.state == STATE_HOWTO:
            return self.howto_menu
        if self.state == STATE_PAUSED:
            return self.pause_menu
        if self.state == STATE_RESULT:
            return self.result_menu
        return None

    def _handle_events(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()
                return

            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11 and not IS_ANDROID:
                self._toggle_fullscreen()
                continue

            if event.type == pygame.VIDEORESIZE:
                # Fires for any resize of a RESIZABLE window (Windows only,
                # see _apply_display_mode_windows) -- both our own maximize/
                # restore and the player manually dragging/snapping/
                # maximizing it themselves land here uniformly.
                self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                constants.WIDTH, constants.HEIGHT = event.size
                self._reflow_for_resolution()
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._handle_escape()
                continue

            if self.state == STATE_PLAYING:
                if self.show_touch:
                    self.touch.handle_event(event)
                continue

            menu = self._active_menu()
            if menu is not None:
                menu.handle_event(event, mouse_pos)

    def _handle_escape(self):
        if self.state == STATE_PLAYING:
            self.touch.release_all()
            self.state = STATE_PAUSED
        elif self.state == STATE_PAUSED:
            self._resume()
        elif self.state in (STATE_SETTINGS,):
            self._close_settings()
        elif self.state == STATE_MODE_SELECT:
            self._close_mode_select()
        elif self.state == STATE_DRONE_SELECT:
            self._close_drone_select()
        elif self.state == STATE_DEFENSE_SELECT:
            self._close_defense_select()
        elif self.state == STATE_ACCOUNT:
            self._close_account()
        elif self.state == STATE_LEADERBOARD:
            self._close_leaderboard()
        elif self.state == STATE_HOWTO:
            self._close_howto()

    def _gather_controls(self):
        keys = pygame.key.get_pressed()
        touch = self.touch.state if self.show_touch else {}
        return {
            "thrust": keys[pygame.K_w] or keys[pygame.K_UP] or touch.get("thrust", False),
            # S / Down arrow: reverse thrust and brake. This is the axis that
            # was missing entirely before.
            "reverse": keys[pygame.K_s] or keys[pygame.K_DOWN] or touch.get("reverse", False),
            "left": keys[pygame.K_a] or keys[pygame.K_LEFT] or touch.get("left", False),
            "right": keys[pygame.K_d] or keys[pygame.K_RIGHT] or touch.get("right", False),
            "ascend": keys[pygame.K_SPACE] or keys[pygame.K_e] or touch.get("ascend", False),
            "descend": (
                keys[pygame.K_LSHIFT]
                or keys[pygame.K_RSHIFT]
                or keys[pygame.K_q]
                or touch.get("descend", False)
            ),
            "fire": (
                keys[pygame.K_f]
                or pygame.mouse.get_pressed()[0]
                or touch.get("fire", False)
            ),
        }

    def _update(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        self._poll_score_submit()

        if self.state == STATE_PLAYING and self.world is not None:
            self.world.update(dt, self._gather_controls())
            if self.world.shake_request > 0.0:
                self.camera.add_shake(self.world.shake_request)
            player = self.world.player
            if player is not None and player.alive:
                # A respawn puts the next airframe at the map edge. Snapping
                # avoids a long disorienting pan across the whole city.
                if player is not self._tracked_player:
                    self.camera.snap_to(player.pos)
                    self._tracked_player = player
                self.camera.follow(player.pos, dt)
            self.camera.update(dt)

            if self.world.result != world_module.RESULT_PLAYING:
                self._finish_mission()
            return

        menu = self._active_menu()
        if menu is not None:
            menu.update(mouse_pos, dt)

    def _finish_mission(self):
        world = self.world
        won = world.result == world_module.RESULT_WON
        mode = world.mode

        self.profile["total_score"] += world.score
        self.profile["best_score"] = max(self.profile["best_score"], world.score)
        if mode == "defense":
            # Air Defense doesn't destroy targets or fight airborne hostiles
            # in the drone-mission sense -- raiders shot down are the closest
            # analog to "enemies destroyed" and feed the same backend field.
            enemies_destroyed = world.raiders_destroyed
            targets_destroyed = 0
        elif mode == "survival":
            # Survival has no combat stats at all -- strikes survived is the
            # closest analog to "targets destroyed" (a completion measure).
            enemies_destroyed = 0
            targets_destroyed = world.strikes_survived
        else:
            self.profile["targets_destroyed"] += world.targets_destroyed
            self.profile["enemies_destroyed"] += world.enemies_destroyed
            enemies_destroyed = world.enemies_destroyed
            targets_destroyed = world.targets_destroyed
        if won:
            self.profile["missions_completed"] += 1

        # Coins/XP/level are tracked locally regardless of account status --
        # signing in just also mirrors the same reward onto the server (see
        # backend/src/levels.js, kept in exact lockstep with src/leveling.py)
        # so a leaderboard entry and a second device both stay accurate.
        xp_gained, coins_gained = leveling.rewards_for_score(world.score)
        level_before = self.profile["level"]
        self.profile["xp"] += xp_gained
        self.profile["coins"] += coins_gained
        self.profile["level"] = leveling.level_for_xp(self.profile["xp"])
        leveled_up = self.profile["level"] > level_before
        self._autosave()

        token = self.account.get("token")
        if token and backend.is_configured():
            self.pending_score_submit = backend.run_async(
                backend.submit_score, token, world.score, won, targets_destroyed, enemies_destroyed
            )

        if mode == "defense":
            summary = [
                ("SCORE", world.score),
                ("STRUCTURES SAVED", f"{world.protected_remaining}/{len(world.protected)}"),
                ("RAIDERS DOWNED", world.raiders_destroyed),
                ("WAVES SURVIVED", f"{world.wave}/{world.wave_total}"),
                ("COINS EARNED", f"+{coins_gained}"),
                ("XP EARNED", f"+{xp_gained}" + ("  LEVEL UP!" if leveled_up else "")),
                ("CAREER TOTAL", self.profile["total_score"]),
            ]
            change_loadout = self._open_defense_select
        elif mode == "survival":
            summary = [
                ("SCORE", world.score),
                ("SURVIVED", "YES" if won else "NO"),
                ("STRIKES SURVIVED", world.strikes_survived),
                ("TIME", f"{world.elapsed:.0f}s / {world.duration:.0f}s"),
                ("COINS EARNED", f"+{coins_gained}"),
                ("XP EARNED", f"+{xp_gained}" + ("  LEVEL UP!" if leveled_up else "")),
                ("CAREER TOTAL", self.profile["total_score"]),
            ]
            change_loadout = self._open_mode_select
        else:
            summary = [
                ("SCORE", world.score),
                ("TARGETS DESTROYED", f"{world.targets_destroyed}/{len(world.targets)}"),
                ("HOSTILES DOWNED", world.enemies_destroyed),
                ("AIR DEFENSE DESTROYED", f"{world.pvo_destroyed}/{world.pvo_total}"),
                ("AIRFRAMES LEFT", world.units_left),
                ("COINS EARNED", f"+{coins_gained}"),
                ("XP EARNED", f"+{xp_gained}" + ("  LEVEL UP!" if leveled_up else "")),
                ("CAREER TOTAL", self.profile["total_score"]),
            ]
            change_loadout = self._open_drone_select

        self.result_menu = ResultMenu(won, summary, self._retry, change_loadout, self._return_to_menu)
        self.state = STATE_RESULT

    def _draw(self):
        if self.state in (STATE_PLAYING, STATE_PAUSED, STATE_RESULT) and self.world is not None:
            self.world.draw(self.screen, self.camera)
            self.hud.draw(
                self.screen,
                self.world,
                self.camera,
                show_fps=self.settings.get("show_fps", False),
                fps=self.clock.get_fps(),
            )
            if self.state == STATE_PLAYING and self.show_touch:
                self.touch.draw(self.screen)
        else:
            self.screen.fill(constants.BG_COLOR)
            self._draw_menu_backdrop()

        menu = self._active_menu()
        if menu is not None and self.state != STATE_PLAYING:
            menu.draw(self.screen)

        pygame.display.flip()

    def _draw_menu_backdrop(self):
        spacing = 48
        for x in range(0, constants.WIDTH, spacing):
            pygame.draw.line(self.screen, constants.GRID_COLOR, (x, 0), (x, constants.HEIGHT))
        for y in range(0, constants.HEIGHT, spacing):
            pygame.draw.line(self.screen, constants.GRID_COLOR, (0, y), (constants.WIDTH, y))
