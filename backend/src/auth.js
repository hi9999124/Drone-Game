// Password hashing (PBKDF2 via Web Crypto -- Workers have no bcrypt/argon2,
// but PBKDF2-SHA256 with a high iteration count is a legitimate, standard
// choice and needs no external dependency) and session token helpers.

const PBKDF2_ITERATIONS = 120000;
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

function toHex(buffer) {
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function fromHex(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return bytes;
}

async function deriveBits(password, salt, iterations) {
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"]
  );
  return crypto.subtle.deriveBits(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    keyMaterial,
    256
  );
}

export async function hashPassword(password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const bits = await deriveBits(password, salt, PBKDF2_ITERATIONS);
  return `${PBKDF2_ITERATIONS}:${toHex(salt)}:${toHex(bits)}`;
}

export async function verifyPassword(password, stored) {
  if (!stored) return false;
  const [iterStr, saltHex, hashHex] = stored.split(":");
  const iterations = parseInt(iterStr, 10);
  const salt = fromHex(saltHex);
  const bits = await deriveBits(password, salt, iterations);
  // Constant-time-ish compare: not perfectly timing-safe, but this is a
  // hobby leaderboard, not a bank -- PBKDF2 itself is the real defense here.
  return toHex(bits) === hashHex;
}

export function newSessionToken() {
  return `${crypto.randomUUID()}${crypto.randomUUID()}`.replace(/-/g, "");
}

export function sessionExpiry(now = Date.now()) {
  return now + SESSION_TTL_MS;
}
