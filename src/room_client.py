"""Stage 4: internet room play over the Cloudflare Worker relay
(backend/src/room.js) instead of a direct LAN/RadminVPN IP (src/net.py).

Needs the optional `websockets` package -- LAN play needs nothing beyond the
standard library and keeps working with no internet at all; this is purely
additive for players who'd rather host/browse/join a room than type an IP.

The relay is deliberately dumb (see room.js's comment): it only pairs two
sockets and forwards messages verbatim. All of the actual match protocol
({"type": "join"/"start"/"input"/"state"/"leave", ...}) is exactly what
src/net.py already speaks over UDP, so game.py's host/join/update logic
doesn't need to know which transport it's running over -- RoomTransport
below just adapts RoomClient's single-pipe send()/poll() to the same
(addr, message) shape as net.UDPTransport.

Runs the blocking websocket connection on a background thread with a
Queue for incoming messages, so the synchronous, once-per-frame poll()
pattern used everywhere else in this codebase doesn't change.
"""

import json
import queue
import threading

try:
    import websockets.sync.client as _ws_client
    from websockets.exceptions import ConnectionClosed as _ConnectionClosed

    HAVE_WEBSOCKETS = True
except ImportError:
    HAVE_WEBSOCKETS = False


def ws_url(api_base, room_code):
    """https://host -> wss://host/room/CODE (http -> ws, for local wrangler
    dev). Room codes are case-insensitive server-side; upper-cased here just
    so what's typed and what's displayed always match."""
    scheme = "wss" if api_base.startswith("https") else "ws"
    rest = api_base.split("://", 1)[1].rstrip("/")
    return f"{scheme}://{rest}/room/{room_code.strip().upper()}"


class RoomClient:
    """One WebSocket connection to a room relay. Connects immediately in
    the background; `connected`/`error` report status so the UI can show
    "Connecting..." without blocking a single frame of the game loop."""

    def __init__(self, url):
        self._in_queue = queue.Queue()
        self._ws = None
        self._connected = False
        self._error = None
        self._closed = False
        if not HAVE_WEBSOCKETS:
            self._error = "The 'websockets' package isn't installed -- run: pip install websockets"
            self._thread = None
            return
        self._thread = threading.Thread(target=self._run, args=(url,), daemon=True)
        self._thread.start()

    def _run(self, url):
        try:
            with _ws_client.connect(url, open_timeout=8) as ws:
                self._ws = ws
                self._connected = True
                while not self._closed:
                    try:
                        data = ws.recv(timeout=1.0)
                    except TimeoutError:
                        continue
                    except _ConnectionClosed:
                        break
                    try:
                        self._in_queue.put(json.loads(data))
                    except (ValueError, UnicodeDecodeError):
                        continue
        except Exception as exc:  # noqa: BLE001 -- surfaced to the UI, not swallowed
            self._error = str(exc)
        finally:
            self._connected = False

    @property
    def connected(self):
        return self._connected

    @property
    def error(self):
        return self._error

    def send(self, message):
        if self._ws is None:
            return
        try:
            self._ws.send(json.dumps(message))
        except Exception:
            pass  # best-effort, same policy as every other transport here

    def poll(self, max_messages=128):
        received = []
        for _ in range(max_messages):
            try:
                received.append(self._in_queue.get_nowait())
            except queue.Empty:
                break
        return received

    def close(self):
        self._closed = True
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass


class RoomTransport:
    """Adapts RoomClient's single-pipe send()/poll() to the (addr, message)
    shape net.UDPTransport uses, so game.py's already-verified _poll_hosting/
    _poll_joining/_update_versus work unmodified regardless of which
    transport backs a match. `addr` is meaningless for a single relay pipe
    -- callers just need it truthy (see game.py's `self._mp_peer_addr`
    checks) and it's ignored on send."""

    def __init__(self, client):
        self._client = client

    @property
    def connected(self):
        return self._client.connected

    @property
    def error(self):
        return self._client.error

    def send(self, _addr, message):
        self._client.send(message)

    def poll(self, max_messages=128):
        return [(True, msg) for msg in self._client.poll(max_messages)]

    def close(self):
        self._client.close()
