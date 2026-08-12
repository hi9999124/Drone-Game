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
import threading
import time
import urllib.error
import urllib.request
import webbrowser

# Fill these in after deploying backend/ -- see backend/README.md.
API_BASE = "https://dronepvo-backend.YOUR-SUBDOMAIN.workers.dev"
GITHUB_CLIENT_ID = "YOUR_GITHUB_CLIENT_ID"

GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"

REQUEST_TIMEOUT = 10


class BackendError(Exception):
    pass


def is_configured():
    """False until API_BASE has actually been set to a real deployment."""
    return "YOUR-SUBDOMAIN" not in API_BASE


def _request(url, payload=None, method="GET", token=None, timeout=REQUEST_TIMEOUT):
    headers = {"Accept": "application/json"}
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
        raise BackendError(body.get("error", f"Server error ({exc.code})")) from exc
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
