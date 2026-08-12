// Stage 4: internet room play. A Cloudflare Worker can't relay raw UDP, and
// full P2P (WebRTC) needs a signalling+STUN/TURN stack that's a lot of
// fragile moving parts for a $0-budget hobby project -- so instead this is a
// plain WebSocket relay: two players' sockets get paired up inside one
// Durable Object (one instance per room code) and every gameplay message is
// forwarded byte-for-byte to the other side, completely opaque to this file.
//
// That's deliberate: src/versus_world.py and game.py's host/join/update
// logic were already built and verified against src/net.py's LAN UDP
// transport (Stage 3) using the message shapes {"type": "join"/"start"/
// "input"/"state"/"leave", ...}. This relay doesn't need to know or care
// about any of that -- it only ever has to get a message from one socket to
// the other, so the exact same Python-side game logic works unchanged
// whether a match is running over LAN UDP or this relay.
//
// RoomRelay: one Durable Object instance per room code (looked up by
// idFromName(code), so the code IS the routing key -- no separate lookup
// table needed). Holds at most two sockets: whoever connects first and
// sends "create_room" is the host; the next socket to send "join_room"
// is the guest. Anything else is relayed verbatim.
export class RoomRelay {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.sockets = new Map(); // WebSocket -> "host" | "guest"
    this.meta = null; // { code, name, isPublic } once the host creates the room
  }

  async fetch(request) {
    if (request.headers.get("Upgrade") !== "websocket") {
      return new Response("Expected a WebSocket upgrade request.", { status: 426 });
    }
    const url = new URL(request.url);
    const code = url.pathname.split("/").filter(Boolean).pop() || "";

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    server.accept();
    server.addEventListener("message", (event) => this._onMessage(server, code, event));
    server.addEventListener("close", () => this._onClose(server));
    server.addEventListener("error", () => this._onClose(server));
    return new Response(null, { status: 101, webSocket: client });
  }

  _onMessage(ws, code, event) {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch {
      return; // malformed frame -- drop it, same policy as the UDP transport
    }

    if (msg.type === "create_room") {
      if (this.meta) {
        ws.send(JSON.stringify({ type: "error", message: "This room already has a host." }));
        ws.close();
        return;
      }
      this.sockets.set(ws, "host");
      this.meta = { code, name: String(msg.name || "Match").slice(0, 40), isPublic: Boolean(msg.public) };
      if (this.meta.isPublic) this._announce(true);
      ws.send(JSON.stringify({ type: "room_ready", code }));
      return;
    }

    if (msg.type === "join_room") {
      if (!this.meta) {
        ws.send(JSON.stringify({ type: "error", message: "Room not found -- check the code." }));
        ws.close();
        return;
      }
      if (this.sockets.size >= 2) {
        ws.send(JSON.stringify({ type: "error", message: "That room is already full." }));
        ws.close();
        return;
      }
      this.sockets.set(ws, "guest");
      ws.send(JSON.stringify({ type: "joined", code }));
      for (const [peer, role] of this.sockets) {
        if (role === "host") peer.send(JSON.stringify({ type: "peer_joined" }));
      }
      return;
    }

    // Opaque gameplay payload (join/start/input/state/leave) -- forward
    // as-is to whichever socket isn't the sender.
    for (const peer of this.sockets.keys()) {
      if (peer !== ws) peer.send(event.data);
    }
  }

  _onClose(ws) {
    const role = this.sockets.get(ws);
    this.sockets.delete(ws);
    for (const peer of this.sockets.keys()) {
      try {
        peer.send(JSON.stringify({ type: "peer_left" }));
      } catch {
        // peer socket already gone -- nothing to notify
      }
    }
    if (role === "host" && this.meta?.isPublic) this._announce(false);
  }

  async _announce(active) {
    if (!this.env.ROOM_DIRECTORY) return;
    const id = this.env.ROOM_DIRECTORY.idFromName("directory");
    const stub = this.env.ROOM_DIRECTORY.get(id);
    try {
      await stub.fetch("https://room-directory/update", {
        method: "POST",
        body: JSON.stringify({ code: this.meta.code, name: this.meta.name, active }),
      });
    } catch {
      // best-effort -- a stale/missing directory entry just means one room
      // doesn't show up in the public browser, not a broken match
    }
  }
}

// RoomDirectory: a single, always-the-same-instance Durable Object
// (idFromName("directory")) that tracks which room codes are currently
// hosting a *public* match, for the "browse public rooms" screen. Private
// rooms never call _announce and so never appear here -- joining one always
// requires already knowing its code.
//
// Backed by transactional storage (not just an in-memory Map) since a Worker
// can evict an idle Durable Object's memory at any time; state.storage
// survives that.
export class RoomDirectory {
  constructor(state) {
    this.state = state;
    this.rooms = null; // Map<code, {name, updated}>, lazy-loaded on first use
  }

  async _load() {
    if (this.rooms) return;
    const stored = await this.state.storage.get("rooms");
    this.rooms = new Map(Object.entries(stored || {}));
  }

  async _save() {
    await this.state.storage.put("rooms", Object.fromEntries(this.rooms));
  }

  async fetch(request) {
    await this._load();
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/update") {
      const { code, name, active } = await request.json();
      if (active) {
        this.rooms.set(code, { name, updated: Date.now() });
      } else {
        this.rooms.delete(code);
      }
      await this._save();
      return new Response("ok");
    }

    if (request.method === "GET" && url.pathname === "/list") {
      // A room whose host disconnected without a clean close (crash, lost
      // connection) never sends active:false -- prune anything stale rather
      // than showing a dead room in the browser forever.
      const staleCutoffMs = 5 * 60 * 1000;
      const now = Date.now();
      let pruned = false;
      for (const [code, info] of this.rooms) {
        if (now - info.updated > staleCutoffMs) {
          this.rooms.delete(code);
          pruned = true;
        }
      }
      if (pruned) await this._save();
      return new Response(
        JSON.stringify({ rooms: [...this.rooms.entries()].map(([code, info]) => ({ code, name: info.name })) }),
        { headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response("Not found", { status: 404 });
  }
}
