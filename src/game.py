import os
import random
import string
import sys

import pygame

from . import backend, constants, drones, leveling, net, room_client, save_system, world as world_module
from .camera import Camera
from .defense_world import DefenseWorld
from .entities import pvo
from .sandbox_world import SandboxWorld
from .survival_world import SurvivalWorld
from .ui.hud import HUD
from .ui.menu import (
    AccountMenu,
    DefenseSelectMenu,
    DroneSelectMenu,
    HostWaitingMenu,
    HowToMenu,
    JoinMultiplayerMenu,
    LeaderboardMenu,
    MainMenu,
    ModeSelectMenu,
    MultiplayerMenu,
    PauseMenu,
    ResultMenu,
    RoomHostWaitingMenu,
    RoomJoinMenu,
    RoomMenu,
    SettingsMenu,
)
from .ui.touch_controls import TouchControls
from .versus_world import VersusWorld

STATE_MENU = "menu"
STATE_MODE_SELECT = "mode_select"
STATE_DRONE_SELECT = "drone_select"
STATE_SANDBOX_SELECT = "sandbox_select"
STATE_DEFENSE_SELECT = "defense_select"
STATE_MP_MENU = "mp_menu"
STATE_MP_HOST_SELECT = "mp_host_select"
STATE_MP_HOSTING = "mp_hosting"
STATE_MP_JOIN = "mp_join"
STATE_ROOM_MENU = "room_menu"
STATE_ROOM_HOST_SELECT = "room_host_select"
STATE_ROOM_HOSTING = "room_hosting"
STATE_ROOM_JOIN = "room_join"
STATE_SETTINGS = "settings"
STATE_ACCOUNT = "account"
STATE_LEADERBOARD = "leaderboard"
STATE_HOWTO = "howto"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_RESULT = "result"

MP_JOIN_TIMEOUT = 8.0
# A Room connection hops through the relay (an extra network round trip
# beyond a direct LAN packet), so it gets more slack before giving up.
ROOM_JOIN_TIMEOUT = 15.0
ROOM_CODE_CHARS = string.ascii_uppercase + string.digits

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
        self.touch = TouchControls(scheme=self.settings.get("touch_scheme", "Stick"))
        self.world = None
        self.state = STATE_MENU
        self.previous_state = STATE_MENU
        self._tracked_player = None

        # Multiplayer connection state -- None whenever no match is being
        # hosted/joined/played. See net.py + versus_world.py.
        self._mp_net = None
        self._mp_peer_addr = None
        self._mp_drone_key = None
        self._mp_pvo_unit_key = None
        self._mp_remote_controls = {}
        self._mp_join_timer = 0.0
        # Room-play (Stage 4) specific connection state -- self._mp_net/
        # self._mp_peer_addr above are shared with LAN play once a match is
        # actually running (see room_client.RoomTransport).
        self._room_is_public = False
        self._room_code = None
        self._room_create_sent = False
        self._room_pvo_unit_key = None
        self._room_join_sent = False

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
            self._open_drone_select,
            self._open_sandbox_select,
            self._open_defense_select,
            self._start_survival_mission,
            self._open_multiplayer_menu,
            self._close_mode_select,
        )
        self.mp_menu = MultiplayerMenu(
            self._open_mp_host_select, self._open_mp_join, self._open_room_menu, self._close_multiplayer_menu
        )
        self.room_menu = RoomMenu(
            self._open_room_host_public, self._open_room_host_private, self._open_room_join, self._close_room_menu
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
        self.sandbox_menu = None
        self.defense_menu = None
        self.mp_host_select_menu = None
        self.host_waiting_menu = None
        self.join_menu = None
        self.room_host_select_menu = None
        self.room_host_waiting_menu = None
        self.room_join_menu = None
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

    def _open_sandbox_select(self):
        # Free Flight uses the same airframe picker as a strike mission --
        # which drone you're flying is the one loadout decision the sandbox
        # still has, and unlocks apply the same way.
        self.sandbox_menu = DroneSelectMenu(
            self.profile,
            self._start_sandbox_session,
            self._close_sandbox_select,
            selected_key=self.profile.get("last_drone"),
        )
        self.previous_state = self.state
        self.state = STATE_SANDBOX_SELECT

    def _close_sandbox_select(self):
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
        elif mode == "sandbox":
            self._open_sandbox_select()
        elif mode in ("survival", "versus"):
            # Survival has no loadout to change; Versus is a live 2-player
            # match, so there's nothing to swap mid-match either -- both
            # just stay paused rather than opening a screen that would make
            # no sense to act on right now.
            pass
        else:
            self._open_drone_select()

    def _open_multiplayer_menu(self):
        self.previous_state = self.state
        self.state = STATE_MP_MENU

    def _close_multiplayer_menu(self):
        self.state = STATE_PAUSED if self.previous_state == STATE_PAUSED else STATE_MODE_SELECT

    def _open_mp_host_select(self):
        self.mp_host_select_menu = DroneSelectMenu(
            self.profile,
            self._host_multiplayer,
            self._close_mp_host_select,
            selected_key=self.profile.get("last_drone"),
        )
        self.previous_state = self.state
        self.state = STATE_MP_HOST_SELECT

    def _close_mp_host_select(self):
        self.state = STATE_MP_MENU

    def _host_multiplayer(self, drone_key):
        self.profile["last_drone"] = drone_key
        self._autosave()
        self._mp_net = net.UDPTransport(port=net.DEFAULT_PORT)
        self._mp_drone_key = drone_key
        self._mp_peer_addr = None
        address_text = f"{net.local_ip_hint()}:{self._mp_net.local_port}"
        self.host_waiting_menu = HostWaitingMenu(address_text, self._cancel_multiplayer)
        self.previous_state = self.state
        self.state = STATE_MP_HOSTING

    def _open_mp_join(self):
        self.join_menu = JoinMultiplayerMenu(self._join_multiplayer, self._close_mp_join)
        self.previous_state = self.state
        self.state = STATE_MP_JOIN

    def _close_mp_join(self):
        self._cancel_multiplayer()

    def _cancel_multiplayer(self):
        if self._mp_net is not None:
            self._mp_net.close()
        self._mp_net = None
        self._mp_peer_addr = None
        self.state = STATE_MP_MENU

    def _join_multiplayer(self, address_text, unit_key):
        try:
            host, port = net.parse_address(address_text)
        except ValueError:
            self.join_menu.status_text = "That doesn't look like a valid address (try IP or IP:port)."
            return
        if self._mp_net is not None:
            self._mp_net.close()
        self._mp_net = net.UDPTransport(port=0)
        self._mp_peer_addr = (host, port)
        self._mp_pvo_unit_key = unit_key
        self._mp_net.send(self._mp_peer_addr, {"type": "join", "pvo_unit": unit_key})
        self._mp_join_timer = MP_JOIN_TIMEOUT
        self.join_menu.status_text = "Connecting..."

    # --------------------------------------------------- multiplayer: rooms
    #
    # Everything past the connection handshake below (_start_versus_match,
    # _update_versus, _finish_versus_match, forfeit-on-leave) is exactly the
    # same code the LAN path above uses -- room_client.RoomTransport adapts
    # a single WebSocket pipe to the same (addr, message) send()/poll()
    # shape as net.UDPTransport, so self._mp_net works identically either
    # way once a match is actually running. Only *getting* two players onto
    # that shared self._mp_net differs: a direct UDP "join" packet doubles
    # as both connection and handshake on LAN, but a Room connection needs
    # its own connect / create_room-or-join_room / wait-for-ack sequence
    # first, driven by _poll_room_hosting/_poll_room_joining below.

    def _open_room_menu(self):
        self.previous_state = self.state
        self.state = STATE_ROOM_MENU

    def _close_room_menu(self):
        self.state = STATE_MP_MENU

    def _open_room_host_public(self):
        self._open_room_host_select(is_public=True)

    def _open_room_host_private(self):
        self._open_room_host_select(is_public=False)

    def _open_room_host_select(self, is_public):
        self.room_host_select_menu = DroneSelectMenu(
            self.profile,
            lambda drone_key: self._host_room(drone_key, is_public),
            self._close_room_host_select,
            selected_key=self.profile.get("last_drone"),
        )
        self.previous_state = self.state
        self.state = STATE_ROOM_HOST_SELECT

    def _close_room_host_select(self):
        self.state = STATE_ROOM_MENU

    def _host_room(self, drone_key, is_public):
        self.profile["last_drone"] = drone_key
        self._autosave()
        code = "".join(random.choices(ROOM_CODE_CHARS, k=6))
        self._mp_drone_key = drone_key
        self._mp_peer_addr = None
        self._room_is_public = is_public
        self._room_code = code
        self._room_create_sent = False
        client = room_client.RoomClient(room_client.ws_url(backend.API_BASE, code))
        self._mp_net = room_client.RoomTransport(client)
        self.room_host_waiting_menu = RoomHostWaitingMenu(is_public, self._cancel_room)
        self.previous_state = self.state
        self.state = STATE_ROOM_HOSTING

    def _open_room_join(self):
        self.room_join_menu = RoomJoinMenu(self._join_room, self._close_room_join)
        self.previous_state = self.state
        self.state = STATE_ROOM_JOIN

    def _close_room_join(self):
        self._cancel_room()

    def _cancel_room(self):
        if self._mp_net is not None:
            self._mp_net.close()
        self._mp_net = None
        self._mp_peer_addr = None
        self.state = STATE_ROOM_MENU

    def _join_room(self, code, unit_key):
        if self._mp_net is not None:
            self._mp_net.close()
        client = room_client.RoomClient(room_client.ws_url(backend.API_BASE, code))
        self._mp_net = room_client.RoomTransport(client)
        self._room_pvo_unit_key = unit_key
        self._room_join_sent = False
        self._mp_join_timer = ROOM_JOIN_TIMEOUT
        self.room_join_menu.status_text = "Connecting..."

    def _poll_room_hosting(self):
        menu = self.room_host_waiting_menu
        if not self._room_create_sent:
            if self._mp_net.error:
                menu.status_text = f"Connection failed: {self._mp_net.error}"
                return
            if not self._mp_net.connected:
                menu.status_text = "Connecting to the relay..."
                return
            display_name = self.account.get("username") or "Match"
            self._mp_net.send(None, {"type": "create_room", "public": self._room_is_public, "name": display_name})
            self._room_create_sent = True
            menu.status_text = "Waiting for room code..."
            return
        for _addr, msg in self._mp_net.poll():
            msg_type = msg.get("type")
            if msg_type == "room_ready":
                self._room_code = msg["code"]
                menu.code_text = self._room_code
                menu.status_text = "Waiting for a player to join..."
            elif msg_type == "error":
                menu.status_text = msg.get("message", "Room error.")
            elif msg_type == "join":
                unit_key = msg.get("pvo_unit", pvo.PVO_UNIT_TYPES[0].key)
                seed = random.randint(0, 2**31 - 1)
                difficulty = self.settings.get("difficulty", "Normal")
                self._mp_peer_addr = True  # sentinel: RoomTransport ignores the addr argument
                self._mp_net.send(
                    self._mp_peer_addr,
                    {"type": "start", "seed": seed, "difficulty": difficulty, "drone_key": self._mp_drone_key},
                )
                self._start_versus_match(
                    seed, difficulty, self._mp_drone_key, unit_key, is_host=True, local_role="drone"
                )
                return

    def _poll_room_joining(self, dt):
        if self._mp_net is None:
            return  # on the JOIN ROOM screen (or timed out/errored already), nothing to poll yet
        self._mp_join_timer -= dt
        menu = self.room_join_menu
        if not self._room_join_sent:
            if self._mp_net.error:
                menu.status_text = f"Connection failed: {self._mp_net.error}"
                return
            if not self._mp_net.connected:
                return
            self._mp_net.send(None, {"type": "join_room"})
            self._room_join_sent = True
            return
        for _addr, msg in self._mp_net.poll():
            msg_type = msg.get("type")
            if msg_type == "joined":
                self._mp_peer_addr = True
                self._mp_net.send(self._mp_peer_addr, {"type": "join", "pvo_unit": self._room_pvo_unit_key})
                menu.status_text = "Connected -- waiting for the host to start..."
            elif msg_type == "error":
                menu.status_text = msg.get("message", "Room error.")
                self._mp_net.close()
                self._mp_net = None
                return
            elif msg_type == "start":
                self._start_versus_match(
                    msg["seed"], msg["difficulty"], msg["drone_key"], self._room_pvo_unit_key,
                    is_host=False, local_role="pvo",
                )
                return
        if self._mp_join_timer <= 0.0 and self.room_join_menu is not None:
            menu.status_text = "No response -- the host may have left."
            self._mp_net.close()
            self._mp_net = None

    def _start_versus_match(self, seed, difficulty, drone_key, pvo_unit_key, is_host, local_role):
        drone_type = drones.get(drone_key)
        unit_type = pvo.PVO_UNITS_BY_KEY.get(pvo_unit_key, pvo.PVO_UNIT_TYPES[0])
        self.world = VersusWorld(drone_type, unit_type, difficulty, seed, is_host=is_host, local_role=local_role)
        self.world.notify(
            "Match started -- destroy the targets" if local_role == "drone" else "Match started -- defend the city",
            duration=4.0,
        )
        self.camera.enable_shake = self.settings.get("screen_shake", True)
        self.camera.snap_to(self.world.player.pos)
        self._tracked_player = self.world.player
        self.touch.release_all()
        self.state = STATE_PLAYING

    def _teardown_multiplayer(self, notify_peer):
        if self._mp_net is None:
            return
        if notify_peer and self._mp_peer_addr is not None:
            self._mp_net.send(self._mp_peer_addr, {"type": "leave"})
        self._mp_net.close()
        self._mp_net = None
        self._mp_peer_addr = None

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
        if key == "touch_scheme":
            # Rebuilds the layout for the new scheme immediately, so the
            # change is visible behind the settings screen rather than on the
            # next launch.
            self.touch.set_scheme(self.settings.get("touch_scheme", "Stick"))
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

    def _start_sandbox_session(self, drone_key):
        drone_type = drones.get(drone_key)
        self.profile["last_drone"] = drone_key
        self._autosave()

        self.world = SandboxWorld(drone_type, self.settings.get("difficulty", "Normal"))
        # Tailored to the airframe, because "how do I actually break something"
        # has a different answer per attack type -- and a ram drone cruising at
        # its spawn altitude of 110 flies straight over every 55-80m block
        # without touching it, which reads as "nothing works" if unexplained.
        if drone_type.attack == "ram":
            hint = "Free flight -- dive into anything below your altitude to level it"
        else:
            hint = "Free flight -- level anything. Ordnance reloads itself"
        self.world.notify(hint, duration=5.0)
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
        elif self.world.mode == "sandbox":
            self._start_sandbox_session(self.profile.get("last_drone", "fpv"))
        else:
            self._start_mission(self.profile.get("last_drone", "fpv"))

    def _resume(self):
        self.touch.release_all()
        self.state = STATE_PLAYING

    def _leave_versus_match(self):
        # "FLY AGAIN"/"CHANGE LOADOUT" after a versus match: there's no
        # sensible instant rematch without a fresh host/join handshake, so
        # both buttons just go back to the multiplayer menu. No "leave"
        # notification needed here -- the peer already has the correct
        # final result from the last snapshot before the match concluded.
        self._teardown_multiplayer(notify_peer=False)
        self._open_multiplayer_menu()

    def _return_to_menu(self):
        if self.world is not None and self.world.mode == "versus":
            self._teardown_multiplayer(notify_peer=True)
        if (
            self.world is not None
            and self.world.mode == "sandbox"
            and self.world.result == world_module.RESULT_PLAYING
        ):
            # A sandbox run has no end condition of its own, so walking away
            # from it IS the end of it: mark it finished and show the same
            # summary screen every other mode gets. RESULT_WON is just "the
            # run concluded" here -- there was nothing to lose.
            self.world.result = world_module.RESULT_WON
            self._finish_mission()
            return
        self.world = None
        self.state = STATE_MENU

    def _quit(self):
        if self.world is not None and self.world.mode == "versus":
            self._teardown_multiplayer(notify_peer=True)
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
        if self.state == STATE_SANDBOX_SELECT:
            return self.sandbox_menu
        if self.state == STATE_DEFENSE_SELECT:
            return self.defense_menu
        if self.state == STATE_MP_MENU:
            return self.mp_menu
        if self.state == STATE_MP_HOST_SELECT:
            return self.mp_host_select_menu
        if self.state == STATE_MP_HOSTING:
            return self.host_waiting_menu
        if self.state == STATE_MP_JOIN:
            return self.join_menu
        if self.state == STATE_ROOM_MENU:
            return self.room_menu
        if self.state == STATE_ROOM_HOST_SELECT:
            return self.room_host_select_menu
        if self.state == STATE_ROOM_HOSTING:
            return self.room_host_waiting_menu
        if self.state == STATE_ROOM_JOIN:
            return self.room_join_menu
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

            # K_AC_BACK is what SDL delivers for an Android device's back
            # gesture/button; it means the same thing as ESC does here.
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_AC_BACK):
                self._handle_escape()
                continue

            if self.state == STATE_PLAYING:
                if self.show_touch:
                    self.touch.handle_event(event)
                    if self.touch.state.get("pause"):
                        # The on-screen pause button -- the only way off a
                        # touchscreen into the pause menu. _handle_escape
                        # releases every held control, which also clears this
                        # button, so it can't re-trigger on the next frame.
                        self._handle_escape()
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
        elif self.state == STATE_SANDBOX_SELECT:
            self._close_sandbox_select()
        elif self.state == STATE_DEFENSE_SELECT:
            self._close_defense_select()
        elif self.state == STATE_MP_MENU:
            self._close_multiplayer_menu()
        elif self.state == STATE_MP_HOST_SELECT:
            self._close_mp_host_select()
        elif self.state == STATE_MP_HOSTING:
            self._cancel_multiplayer()
        elif self.state == STATE_MP_JOIN:
            self._close_mp_join()
        elif self.state == STATE_ROOM_MENU:
            self._close_room_menu()
        elif self.state == STATE_ROOM_HOST_SELECT:
            self._close_room_host_select()
        elif self.state == STATE_ROOM_HOSTING:
            self._cancel_room()
        elif self.state == STATE_ROOM_JOIN:
            self._close_room_join()
        elif self.state == STATE_ACCOUNT:
            self._close_account()
        elif self.state == STATE_LEADERBOARD:
            self._close_leaderboard()
        elif self.state == STATE_HOWTO:
            self._close_howto()

    def _gather_controls(self):
        keys = pygame.key.get_pressed()
        touch = self.touch.state if self.show_touch else {}
        # Analog stick, only when it's actually deflected: a centred (or
        # absent) stick has to stay out of the dict entirely so the keyboard
        # keeps full control of the same frame.
        stick = touch.get("stick")
        if stick is not None and (stick[0] or stick[1]):
            stick_value = stick
        else:
            stick_value = None
        return {
            "stick": stick_value,
            "look": touch.get("look", (0.0, 0.0)),
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
                # Only when the on-screen controls are hidden: SDL synthesizes
                # mouse events from touches, so on a phone "any button held"
                # reads as "left mouse held" -- which would mean steering the
                # joystick continuously dropped bombs. With the pads visible,
                # the FIRE button is the way to fire.
                or (not self.show_touch and pygame.mouse.get_pressed()[0])
                or touch.get("fire", False)
            ),
        }

    def _update(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        self._poll_score_submit()

        if self.state == STATE_MP_HOSTING:
            self._poll_hosting()
            menu = self._active_menu()
            if menu is not None:
                menu.update(mouse_pos, dt)
            return

        if self.state == STATE_MP_JOIN:
            self._poll_joining(dt)
            menu = self._active_menu()
            if menu is not None:
                menu.update(mouse_pos, dt)
            return

        if self.state == STATE_ROOM_HOSTING:
            self._poll_room_hosting()
            menu = self._active_menu()
            if menu is not None:
                menu.update(mouse_pos, dt)
            return

        if self.state == STATE_ROOM_JOIN:
            self._poll_room_joining(dt)
            menu = self._active_menu()
            if menu is not None:
                menu.update(mouse_pos, dt)
            return

        if self.state == STATE_PLAYING and self.world is not None:
            if self.world.mode == "versus":
                self._update_versus(dt)
            else:
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
            # The camera pad pans the view away from the drone while held and
            # springs back when released (see Camera.set_look).
            self.camera.set_look(self.touch.state.get("look") if self.show_touch else None)
            self.camera.update(dt)

            if self.world.result != world_module.RESULT_PLAYING:
                self._finish_mission()
            return

        menu = self._active_menu()
        if menu is not None:
            menu.update(mouse_pos, dt)

    def _poll_hosting(self):
        for addr, msg in self._mp_net.poll():
            if msg.get("type") == "join":
                self._mp_peer_addr = addr
                unit_key = msg.get("pvo_unit", pvo.PVO_UNIT_TYPES[0].key)
                seed = random.randint(0, 2**31 - 1)
                difficulty = self.settings.get("difficulty", "Normal")
                self._mp_net.send(
                    addr, {"type": "start", "seed": seed, "difficulty": difficulty, "drone_key": self._mp_drone_key}
                )
                self._start_versus_match(
                    seed, difficulty, self._mp_drone_key, unit_key, is_host=True, local_role="drone"
                )
                return

    def _poll_joining(self, dt):
        if self._mp_net is None:
            return  # on the JOIN screen, but CONNECT hasn't been pressed yet
        self._mp_join_timer -= dt
        for addr, msg in self._mp_net.poll():
            if msg.get("type") == "start":
                self._start_versus_match(
                    msg["seed"], msg["difficulty"], msg["drone_key"], self._mp_pvo_unit_key,
                    is_host=False, local_role="pvo",
                )
                return
        if self._mp_join_timer <= 0.0 and self.join_menu is not None:
            self.join_menu.status_text = "No response -- check the address and that the host is still waiting."
            self._mp_net.close()
            self._mp_net = None

    def _update_versus(self, dt):
        world = self.world
        local_controls = self._gather_controls()
        if world.is_host:
            for _addr, msg in self._mp_net.poll():
                msg_type = msg.get("type")
                if msg_type == "input":
                    self._mp_remote_controls = msg
                elif msg_type == "leave":
                    world.result = world_module.RESULT_WON  # the PVO side forfeited -- Drone wins
            drone_controls = local_controls if world.local_role == "drone" else self._mp_remote_controls
            pvo_controls = self._mp_remote_controls if world.local_role == "drone" else local_controls
            world.host_update(dt, drone_controls, pvo_controls)
            if self._mp_peer_addr is not None:
                self._mp_net.send(self._mp_peer_addr, {"type": "state", **world.build_snapshot()})
        else:
            if self._mp_peer_addr is not None:
                self._mp_net.send(self._mp_peer_addr, {"type": "input", **local_controls})
            for _addr, msg in self._mp_net.poll():
                msg_type = msg.get("type")
                if msg_type == "state":
                    world.apply_snapshot({k: v for k, v in msg.items() if k != "type"})
                elif msg_type == "leave":
                    world.result = world_module.RESULT_LOST  # the Drone side forfeited -- PVO wins

    def _finish_mission(self):
        world = self.world
        mode = world.mode
        if mode == "versus":
            self._finish_versus_match()
            return
        if mode == "sandbox":
            self._finish_sandbox_session()
            return
        won = world.result == world_module.RESULT_WON

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

    def _finish_sandbox_session(self):
        """Free Flight is practice, not a career mission.

        It deliberately awards no coins, XP or career score and never touches
        the leaderboard: the city is defenceless and the run is unbounded, so
        any reward it paid out would be farmable by simply flying for longer,
        which would make every ranked number next to it meaningless. The
        summary is the reward.
        """
        world = self.world
        summary = [
            ("SESSION SCORE", world.score),
            ("BLOCKS LEVELLED", f"{world.blocks_destroyed}/{world.block_total}"),
            ("CITY DESTROYED", f"{world.destruction_fraction * 100:.0f}%"),
            ("PROPS DESTROYED", f"{world.props_destroyed}/{world.prop_total}"),
            ("AIRFRAMES LOST", world.airframes_lost),
            ("CAREER REWARDS", "NONE (SANDBOX)"),
        ]
        self.result_menu = ResultMenu(
            True,
            summary,
            lambda: self._start_sandbox_session(self.profile.get("last_drone", "fpv")),
            self._open_sandbox_select,
            self._return_to_menu,
        )
        self.state = STATE_RESULT

    def _finish_versus_match(self):
        # RESULT_WON/RESULT_LOST in VersusWorld are always framed from the
        # Drone side's perspective (WON = drone won) -- reframe per which
        # side THIS player actually played before touching any reward math.
        world = self.world
        is_drone = world.local_role == "drone"
        won = (world.result == world_module.RESULT_WON) if is_drone else (world.result == world_module.RESULT_LOST)
        local_score = world.score if is_drone else world.pvo_score

        self.profile["total_score"] += local_score
        self.profile["best_score"] = max(self.profile["best_score"], local_score)
        if won:
            self.profile["missions_completed"] += 1

        xp_gained, coins_gained = leveling.rewards_for_score(local_score)
        level_before = self.profile["level"]
        self.profile["xp"] += xp_gained
        self.profile["coins"] += coins_gained
        self.profile["level"] = leveling.level_for_xp(self.profile["xp"])
        leveled_up = self.profile["level"] > level_before
        self._autosave()

        token = self.account.get("token")
        if token and backend.is_configured():
            targets_destroyed = (len(world.targets) - world.targets_remaining) if is_drone else 0
            airframes_downed = world.drone_type.units - world.drone_units_left if not is_drone else 0
            self.pending_score_submit = backend.run_async(
                backend.submit_score, token, local_score, won, targets_destroyed, airframes_downed
            )

        if is_drone:
            summary = [
                ("SCORE", local_score),
                ("RESULT", "DRONE WINS" if won else "PVO WINS"),
                ("TARGETS DESTROYED", f"{len(world.targets) - world.targets_remaining}/{len(world.targets)}"),
                ("AIRFRAMES LEFT", world.drone_units_left),
                ("COINS EARNED", f"+{coins_gained}"),
                ("XP EARNED", f"+{xp_gained}" + ("  LEVEL UP!" if leveled_up else "")),
                ("CAREER TOTAL", self.profile["total_score"]),
            ]
        else:
            summary = [
                ("SCORE", local_score),
                ("RESULT", "PVO WINS" if won else "DRONE WINS"),
                ("AIRFRAMES DOWNED", world.drone_type.units - world.drone_units_left),
                ("TURRET STATUS", "STANDING" if world.turret.alive_and_well else "DESTROYED"),
                ("COINS EARNED", f"+{coins_gained}"),
                ("XP EARNED", f"+{xp_gained}" + ("  LEVEL UP!" if leveled_up else "")),
                ("CAREER TOTAL", self.profile["total_score"]),
            ]

        self.result_menu = ResultMenu(won, summary, self._leave_versus_match, self._leave_versus_match, self._return_to_menu)
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
