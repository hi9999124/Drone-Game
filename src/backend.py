"""HTTP client for the optional Cloudflare Worker backend (backend/).

Everything here is best-effort and optional: the game is fully playable
offline with no account, and every function either returns a result or
raises BackendError -- callers are expected to catch that and fall back to
local-only play, never to crash the game over a network hiccup.

GitHub and Google sign-in both use OAuth "device flow" (the same pattern
`gh auth login` uses): the desktop app has no way to receive a browser
redirect, so instead it shows a short code, opens the provider's approval
page in the system browser, and polls until the user finishes approving on
whatever device they're looking at. See backend/README.md for exactly what
to paste in below once the Worker is deployed.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from . import save_system

DEFAULT_API_BASE = "https://dronepvo-backend.YOUR-SUBDOMAIN.workers.dev"
DEFAULT_GITHUB_CLIENT_ID = "YOUR_GITHUB_CLIENT_ID"

GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"

REQUEST_TIMEOUT = 10

CONFIG_PATH = os.path.join(save_system.save_dir(), "backend_config.json")


CONFIG_ERROR = None  # set by _load_client_config() if the file exists but doesn't parse


def _write_default_config():
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "_readme": (
                        "Edit api_base to your deployed Cloudflare Worker URL "
                        "(see backend/README.md), then restart the game."
                    ),
                    "api_base": DEFAULT_API_BASE,
                    "github_client_id": DEFAULT_GITHUB_CLIENT_ID,
                },
                handle,
                indent=2,
            )
    except OSError:
        pass  # Read-only filesystem, etc. -- defaults still work, just can't be edited here.


def _load_client_config():
    """API_BASE/GITHUB_CLIENT_ID live in an editable JSON file next to the
    save, not hardcoded Python constants -- a downloaded/built .exe has its
    source baked in by PyInstaller at build time, so anyone who deploys
    their own backend needs a way to point an already-built game at it
    without rebuilding from source. Creates the file with placeholder
    values on first run so there's something to find and edit.

    Critically: a file that exists but fails to parse is NEVER overwritten
    here. Silently resetting an unparseable file back to placeholder
    defaults would erase the player's edit over one stray comma with zero
    indication why their sign-in "stopped working" -- instead this leaves
    the broken file exactly as they left it and surfaces CONFIG_ERROR so
    the UI can say what's actually wrong.
    """
    global CONFIG_ERROR
    defaults = {"api_base": DEFAULT_API_BASE, "github_client_id": DEFAULT_GITHUB_CLIENT_ID}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except FileNotFoundError:
        _write_default_config()
        return defaults
    except OSError as exc:
        CONFIG_ERROR = f"Could not read {CONFIG_PATH}: {exc}"
        return defaults

    try:
        loaded = json.loads(raw)
    except ValueError as exc:
        CONFIG_ERROR = f"backend_config.json has invalid JSON ({exc}) -- using defaults until it's fixed."
        return defaults

    return {**defaults, **{k: v for k, v in loaded.items() if k in defaults}}


_config = _load_client_config()
API_BASE = _config["api_base"]
GITHUB_CLIENT_ID = _config["github_client_id"]


class BackendError(Exception):
    pass


def is_configured():
    """False until API_BASE has actually been set to a real deployment."""
    return "YOUR-SUBDOMAIN" not in API_BASE


def _request(url, payload=None, method="GET", token=None, timeout=REQUEST_TIMEOUT):
    # Without an explicit User-Agent, urllib sends "Python-urllib/3.x" --
    # a well-known non-browser signature that Cloudflare's platform-level
    # bot protection on shared *.workers.dev domains blocks by default
    # (browsers pass, scripts get a 403), independent of anything the
    # Worker code itself does. A normal-looking one is enough to pass that
    # check -- this isn't evading anything, it's our own client talking to
    # our own deployed backend.
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; DronePVO/1.0)",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            body = {}
        message = body.get("error", f"Server error ({exc.code})")
        # A generic "Internal error" is useless for actually fixing anything
        # -- the Worker's own detail (e.g. the real JS exception) is far
        # more actionable, both for the player to screenshot and for anyone
        # debugging their own deployment.
        if body.get("detail"):
            message = f"{message} ({body['detail']})"
        raise BackendError(message) from exc
    except urllib.error.URLError as exc:
        raise BackendError(f"Could not reach server: {exc.reason}") from exc
    except TimeoutError as exc:
        raise BackendError("Server took too long to respond.") from exc


# --------------------------------------------------------------- simple auth


def signup(username, password):
    return _request(f"{API_BASE}/auth/signup", {"username": username, "password": password}, method="POST")


def login(username, password):
    return _request(f"{API_BASE}/auth/login", {"username": username, "password": password}, method="POST")


def get_me(token):
    return _request(f"{API_BASE}/me", token=token)


def submit_score(token, score, won, targets_destroyed, enemies_destroyed):
    return _request(
        f"{API_BASE}/score",
        {
            "score": score,
            "won": won,
            "targets_destroyed": targets_destroyed,
            "enemies_destroyed": enemies_destroyed,
        },
        method="POST",
        token=token,
    )


def fetch_leaderboard(limit=20):
    return _request(f"{API_BASE}/leaderboard?limit={limit}")


class AsyncResult:
    """Polled once per frame by a menu -- lets any blocking call (signup,
    login, fetch_leaderboard) run off the main thread without every caller
    needing its own bespoke thread/state plumbing like the device flows."""

    def __init__(self):
        self.done = False
        self.error = None
        self.value = None


def run_async(fn, *args, **kwargs):
    result = AsyncResult()

    def _runner():
        try:
            result.value = fn(*args, **kwargs)
        except BackendError as exc:
            result.error = str(exc)
        finally:
            result.done = True

    threading.Thread(target=_runner, daemon=True).start()
    return result


# --------------------------------------------------------- device-flow login


class DeviceLoginState:
    """Status a menu screen polls once per frame while a login runs on a
    background thread. Only ever written by that one thread and read by the
    main thread, so plain attributes are enough -- no lock needed for this
    (each attribute write/read is atomic under the GIL, and nothing here
    depends on multiple attributes being consistent with each other at the
    exact same instant)."""

    def __init__(self):
        self.status = "idle"  # idle -> starting -> waiting -> done / error
        self.message = ""
        self.user_code = None
        self.verification_uri = None
        self.result = None  # {"token": ..., "profile": ...} once status == "done"

    def reset(self):
        self.__init__()


def start_github_login(state: DeviceLoginState):
    thread = threading.Thread(target=_run_github_login, args=(state,), daemon=True)
    thread.start()


def start_google_login(state: DeviceLoginState):
    thread = threading.Thread(target=_run_google_login, args=(state,), daemon=True)
    thread.start()


def _run_github_login(state: DeviceLoginState):
    state.status = "starting"
    try:
        data = _request(
            GITHUB_DEVICE_CODE_URL,
            {"client_id": GITHUB_CLIENT_ID, "scope": "read:user"},
            method="POST",
        )
    except BackendError as exc:
        state.status, state.message = "error", str(exc)
        return

    state.user_code = data["user_code"]
    state.verification_uri = data["verification_uri"]
    state.status = "waiting"
    state.message = f"Enter code {data['user_code']} at {data['verification_uri']}"
    webbrowser.open(data["verification_uri"])

    interval = data.get("interval", 5)
    deadline = time.monotonic() + data.get("expires_in", 900)

    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            token_data = _request(
                GITHUB_TOKEN_URL,
                {
                    "client_id": GITHUB_CLIENT_ID,
                    "device_code": data["device_code"],
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                method="POST",
            )
        except BackendError as exc:
            state.status, state.message = "error", str(exc)
            return

        error = token_data.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error:
            state.status, state.message = "error", error
            return

        try:
            result = _request(
                f"{API_BASE}/auth/github/complete",
                {"access_token": token_data["access_token"]},
                method="POST",
            )
        except BackendError as exc:
            state.status, state.message = "error", str(exc)
            return

        state.result = result
        state.status = "done"
        return

    state.status, state.message = "error", "GitHub login timed out."


def _run_google_login(state: DeviceLoginState):
    state.status = "starting"
    try:
        data = _request(f"{API_BASE}/auth/google/device/start", {}, method="POST")
    except BackendError as exc:
        state.status, state.message = "error", str(exc)
        return
    if "error" in data:
        state.status, state.message = "error", data["error"]
        return

    state.user_code = data["user_code"]
    state.verification_uri = data.get("verification_url", "https://www.google.com/device")
    state.status = "waiting"
    state.message = f"Enter code {data['user_code']} at {state.verification_uri}"
    webbrowser.open(state.verification_uri)

    interval = data.get("interval", 5)
    deadline = time.monotonic() + data.get("expires_in", 900)

    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            poll = _request(
                f"{API_BASE}/auth/google/device/poll",
                {"device_code": data["device_code"]},
                method="POST",
            )
        except BackendError as exc:
            state.status, state.message = "error", str(exc)
            return

        status = poll.get("status")
        if status == "pending":
            continue
        if status == "slow_down":
            interval += 5
            continue
        if status == "ok":
            state.result = poll
            state.status = "done"
            return
        state.status, state.message = "error", poll.get("error", "Google login failed.")
        return

    state.status, state.message = "error", "Google login timed out."
