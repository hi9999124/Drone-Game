import os
import sys

import pygame

from . import backend, constants, drones, leveling, save_system, world as world_module
from .camera import Camera
from .ui.hud import HUD
from .ui.menu import (
    AccountMenu,
    DroneSelectMenu,
    LeaderboardMenu,
    MainMenu,
    PauseMenu,
    ResultMenu,
    SettingsMenu,
)
from .ui.touch_controls import TouchControls

STATE_MENU = "menu"
STATE_DRONE_SELECT = "drone_select"
STATE_SETTINGS = "settings"
STATE_ACCOUNT = "account"
STATE_LEADERBOARD = "leaderboard"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_RESULT = "result"

# python-for-android sets this env var; it's the standard way to detect
# "running as a packaged Android app" from within the app itself.
IS_ANDROID = "ANDROID_ARGUMENT" in os.environ


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Drone / PVO")

        self.data = save_system.load()
        self.profile = self.data["profile"]
        self.account = self.data["account"]
        self.settings = self.data["settings"]
        self.pending_score_submit = None

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
            self._open_drone_select,
            self._open_account,
            self._open_leaderboard,
            self._open_settings,
            self._quit,
        )
        self.pause_menu = PauseMenu(
            self._resume,
            self._open_drone_select,
            self._open_settings,
            self._return_to_menu,
            self._quit,
        )
        self.settings_menu = SettingsMenu(
            self.settings, self._close_settings, self._on_settings_changed, show_fullscreen_option=not IS_ANDROID
        )
        self.drone_menu = None
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
        # Back out to wherever we came from: the main menu, or a paused mission.
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
        # Genuinely change resolution (like the Android branch above always
        # has) rather than stretching a fixed 1280x720 buffer to fit --
        # SCALED was tried first and made fullscreen look blurry/pixelated
        # since it's still only ever rendering at the windowed resolution.
        # constants.WIDTH/HEIGHT get overwritten to match, and every menu's
        # cached layout is rebuilt below so it's sharp at the real size.
        #
        # pygame.FULLSCREEN alone was tried next and does a *real* OS-level
        # display mode switch on some Windows/driver combinations -- which
        # is exactly what caused the reported black-screen flash and every
        # other fullscreen app on the machine getting kicked out of its own
        # exclusive fullscreen when toggling back. A borderless window sized
        # to exactly cover the desktop (no NOFRAME->real-fullscreen mode
        # switch involved at all) gets the same visual result without ever
        # touching the display's actual video mode.
        fullscreen = self.settings.get("fullscreen", False)
        try:
            if fullscreen:
                # pygame.display.Info() reports the *current window's* size
                # once one already exists (always true here -- a windowed
                # surface is created at startup), not the real desktop size,
                # which would have made this a no-op borderless window
                # rather than a fullscreen one. get_desktop_sizes() reads
                # the actual display mode regardless of window state.
                desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
                os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
                self.screen = pygame.display.set_mode((desktop_w, desktop_h), pygame.NOFRAME)
            else:
                os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
                self.screen = pygame.display.set_mode((constants.WINDOWED_WIDTH, constants.WINDOWED_HEIGHT))
        except pygame.error:
            # No usable display (e.g. SDL's "dummy" video driver, used for
            # headless testing) -- fall back rather than crashing. Only ever
            # happens off a real display anyway.
            self.settings["fullscreen"] = False
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
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
        self.camera.enable_shake = self.settings.get("screen_shake", True)
        self.camera.snap_to(self.world.player.pos)
        self._tracked_player = self.world.player
        self.touch.release_all()
        self.state = STATE_PLAYING

    def _retry(self):
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
        if self.state == STATE_DRONE_SELECT:
            return self.drone_menu
        if self.state == STATE_SETTINGS:
            return self.settings_menu
        if self.state == STATE_ACCOUNT:
            return self.account_menu
        if self.state == STATE_LEADERBOARD:
            return self.leaderboard_menu
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
        elif self.state == STATE_DRONE_SELECT:
            self._close_drone_select()
        elif self.state == STATE_ACCOUNT:
            self._close_account()
        elif self.state == STATE_LEADERBOARD:
            self._close_leaderboard()

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

        self.profile["total_score"] += world.score
        self.profile["best_score"] = max(self.profile["best_score"], world.score)
        self.profile["targets_destroyed"] += world.targets_destroyed
        self.profile["enemies_destroyed"] += world.enemies_destroyed
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
                backend.submit_score, token, world.score, won, world.targets_destroyed, world.enemies_destroyed
            )

        summary = [
            ("SCORE", world.score),
            ("TARGETS DESTROYED", f"{world.targets_destroyed}/{len(world.targets)}"),
            ("HOSTILES DOWNED", world.enemies_destroyed),
            ("AIRFRAMES LEFT", world.units_left),
            ("COINS EARNED", f"+{coins_gained}"),
            ("XP EARNED", f"+{xp_gained}" + ("  LEVEL UP!" if leveled_up else "")),
            ("CAREER TOTAL", self.profile["total_score"]),
        ]
        self.result_menu = ResultMenu(won, summary, self._retry, self._open_drone_select, self._return_to_menu)
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
