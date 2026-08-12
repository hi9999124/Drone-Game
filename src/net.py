"""LAN/RadminVPN multiplayer transport: JSON-over-UDP, host-authoritative.

Why UDP + JSON instead of anything fancier: Python has no batteries-included
game netcode, and this is a fast but not hyper-competitive arcade game -- an
occasional dropped or out-of-order packet just means one frame's snapshot
gets skipped, imperceptible at the ~20-30Hz this sends at. TCP's stall-until-
retransmit behavior would actually be worse here (a lost packet blocking
every later one until it's resent), which is exactly why real-time games
use UDP. JSON is human-debuggable and needs zero external dependencies,
matching the project's $0/no-bloat approach -- worth optimizing to a binary
format later if bandwidth ever actually becomes a problem, not before.

RadminVPN (or Hamachi, etc.) needs no special integration at all: those
tools make a remote machine's IP look like it's on the local LAN, so "LAN
play" and "play over RadminVPN with a friend" are the exact same code path
here, just a different IP typed into the Join screen.
"""

import json
import socket

DEFAULT_PORT = 47321


class UDPTransport:
    """Thin non-blocking UDP wrapper: JSON-encoded dict messages in, dict
    messages out. Polled once per frame from the main loop rather than on a
    background thread -- there's exactly one place networked state can
    change, so nothing here needs a lock.
    """

    def __init__(self, port=0, bind_addr=""):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.bind((bind_addr, port))
        self.local_port = self.sock.getsockname()[1]

    def send(self, addr, message):
        try:
            self.sock.sendto(json.dumps(message).encode("utf-8"), addr)
        except OSError:
            pass  # Best-effort, same as every other UDP send -- a dropped
            # packet here is just a skipped frame of state, not an error
            # worth surfacing to the player.

    def poll(self, max_messages=128):
        """Returns [(addr, message_dict), ...] received since the last
        call. Never blocks; malformed or truncated packets are dropped
        silently rather than crashing the game over a corrupted frame."""
        received = []
        for _ in range(max_messages):
            try:
                data, addr = self.sock.recvfrom(65536)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            try:
                received.append((addr, json.loads(data.decode("utf-8"))))
            except (ValueError, UnicodeDecodeError):
                continue
        return received

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def local_ip_hint():
    """Best-effort LAN IP to show the hosting player -- what to tell a
    friend to connect to. Doesn't actually send any data: "connecting" a UDP
    socket just asks the OS to pick the right local interface/route for that
    destination, a standard trick that works even without real internet
    access (nothing is transmitted for UDP connect())."""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
        probe.close()
        return ip
    except OSError:
        return "127.0.0.1"


def parse_address(text, default_port=DEFAULT_PORT):
    """"host" or "host:port" -> (host, port). Raises ValueError on a bad
    port so the caller can show a real error instead of silently defaulting."""
    text = text.strip()
    if ":" in text:
        host, port_str = text.rsplit(":", 1)
        return host or "127.0.0.1", int(port_str)
    return text, default_port
