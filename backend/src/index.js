import { hashPassword, verifyPassword, newSessionToken, sessionExpiry } from "./auth.js";
import {
  getUserByUsername,
  getUserByGithubId,
  getUserByGoogleSub,
  getUserById,
  createUser,
  getProfile,
  createSession,
  getSession,
  applyMissionResult,
  setProfileLevel,
  topByScore,
} from "./db.js";
import { levelForXp, rankForLevel, rewardsForScore } from "./levels.js";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

function badRequest(message) {
  return json({ error: message }, 400);
}

function unauthorized(message = "Not signed in") {
  return json({ error: message }, 401);
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

function isValidUsername(name) {
  return typeof name === "string" && /^[a-zA-Z0-9_]{3,20}$/.test(name);
}

async function profileWithRank(db, userId) {
  const profile = await getProfile(db, userId);
  return { ...profile, rank: rankForLevel(profile.level) };
}

async function issueSession(db, userId) {
  const token = newSessionToken();
  await createSession(db, userId, token, sessionExpiry());
  return token;
}

async function requireUser(request, env) {
  const auth = request.headers.get("Authorization") || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : null;
  if (!token) return null;
  const session = await getSession(env.DB, token);
  if (!session) return null;
  return getUserById(env.DB, session.user_id);
}

// -------------------------------------------------------------- auth: local

async function handleSignup(request, env) {
  const { username, password } = await readJson(request);
  if (!isValidUsername(username)) {
    return badRequest("Username must be 3-20 characters: letters, numbers, underscore.");
  }
  if (typeof password !== "string" || password.length < 8) {
    return badRequest("Password must be at least 8 characters.");
  }
  if (await getUserByUsername(env.DB, username)) {
    return badRequest("That username is taken.");
  }

  const passwordHash = await hashPassword(password);
  const userId = await createUser(env.DB, { username, passwordHash });
  const token = await issueSession(env.DB, userId);
  return json({ token, username, profile: await profileWithRank(env.DB, userId) });
}

async function handleLogin(request, env) {
  const { username, password } = await readJson(request);
  const user = await getUserByUsername(env.DB, username);
  if (!user || !(await verifyPassword(password, user.password_hash))) {
    return unauthorized("Wrong username or password.");
  }
  const token = await issueSession(env.DB, user.id);
  return json({ token, username: user.username, profile: await profileWithRank(env.DB, user.id) });
}

// ------------------------------------------------------------- auth: github
//
// GitHub's OAuth *device flow* needs no client secret (it's designed for
// public clients like a CLI or desktop app), so the desktop game talks to
// GitHub directly to get an access token, then hands that token here just
// to be verified and turned into a session -- the Worker never needs a
// GitHub secret at all for this provider.

async function handleGithubComplete(request, env) {
  const { access_token: accessToken } = await readJson(request);
  if (!accessToken) return badRequest("Missing access_token.");

  const ghResponse = await fetch("https://api.github.com/user", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "User-Agent": "DronePVO",
      Accept: "application/vnd.github+json",
    },
  });
  if (!ghResponse.ok) return unauthorized("GitHub token was not accepted by GitHub.");
  const ghUser = await ghResponse.json();
  const githubId = String(ghUser.id);

  let user = await getUserByGithubId(env.DB, githubId);
  if (!user) {
    const username = await pickAvailableUsername(env.DB, ghUser.login);
    const userId = await createUser(env.DB, { username, email: ghUser.email, githubId });
    user = await getUserById(env.DB, userId);
  }

  const token = await issueSession(env.DB, user.id);
  return json({ token, username: user.username, profile: await profileWithRank(env.DB, user.id) });
}

// ------------------------------------------------------------- auth: google
//
// Google's device flow (for "TV and Limited Input" clients) DOES require a
// client secret for the token exchange, so unlike GitHub, the Worker
// proxies the whole flow and keeps GOOGLE_CLIENT_SECRET server-side --
// the desktop app never sees it.

async function handleGoogleDeviceStart(request, env) {
  if (!env.GOOGLE_CLIENT_ID) {
    return json({ error: "Google sign-in is not configured on this server yet." }, 501);
  }
  const response = await fetch("https://oauth2.googleapis.com/device/code", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: env.GOOGLE_CLIENT_ID,
      scope: "openid email profile",
    }),
  });
  const data = await response.json();
  if (!response.ok) return json({ error: data.error_description || "Google rejected the request." }, 502);
  return json(data);
}

async function handleGoogleDevicePoll(request, env) {
  const { device_code: deviceCode } = await readJson(request);
  if (!deviceCode) return badRequest("Missing device_code.");

  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: env.GOOGLE_CLIENT_ID,
      client_secret: env.GOOGLE_CLIENT_SECRET,
      device_code: deviceCode,
      grant_type: "urn:ietf:params:oauth:grant-type:device_code",
    }),
  });
  const data = await response.json();

  if (!response.ok) {
    // authorization_pending / slow_down are expected while the user hasn't
    // finished approving yet -- not real errors, just "keep polling".
    if (data.error === "authorization_pending" || data.error === "slow_down") {
      return json({ status: data.error });
    }
    return json({ status: "error", error: data.error_description || data.error }, 200);
  }

  const idToken = decodeJwtPayload(data.id_token);
  if (!idToken || !idToken.sub) return json({ status: "error", error: "Google did not return an ID token." });

  let user = await getUserByGoogleSub(env.DB, idToken.sub);
  if (!user) {
    const preferredName = idToken.email ? idToken.email.split("@")[0] : `player${idToken.sub.slice(-6)}`;
    const username = await pickAvailableUsername(env.DB, preferredName);
    const userId = await createUser(env.DB, { username, email: idToken.email, googleSub: idToken.sub });
    user = await getUserById(env.DB, userId);
  }

  const token = await issueSession(env.DB, user.id);
  return json({ status: "ok", token, username: user.username, profile: await profileWithRank(env.DB, user.id) });
}

function decodeJwtPayload(jwt) {
  try {
    const payload = jwt.split(".")[1];
    const padded = payload.replace(/-/g, "+").replace(/_/g, "/").padEnd(payload.length + ((4 - (payload.length % 4)) % 4), "=");
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

async function pickAvailableUsername(db, preferred) {
  const base = (preferred || "player").toLowerCase().replace(/[^a-z0-9_]/g, "").slice(0, 15) || "player";
  let candidate = base;
  let suffix = 0;
  while (await getUserByUsername(db, candidate)) {
    suffix += 1;
    candidate = `${base}${suffix}`;
  }
  return candidate;
}

// ---------------------------------------------------------------- gameplay

async function handleMe(request, env) {
  const user = await requireUser(request, env);
  if (!user) return unauthorized();
  return json({ username: user.username, profile: await profileWithRank(env.DB, user.id) });
}

async function handleScore(request, env) {
  const user = await requireUser(request, env);
  if (!user) return unauthorized();

  const body = await readJson(request);
  const score = Math.max(0, Math.floor(Number(body.score) || 0));
  const { xp, coins } = rewardsForScore(score);

  const before = await getProfile(env.DB, user.id);
  const after = await applyMissionResult(env.DB, user.id, {
    xpGained: xp,
    coinsGained: coins,
    score,
    won: Boolean(body.won),
    targetsDestroyed: Math.max(0, Math.floor(Number(body.targets_destroyed) || 0)),
    enemiesDestroyed: Math.max(0, Math.floor(Number(body.enemies_destroyed) || 0)),
  });

  const newLevel = levelForXp(after.xp);
  const leveledUp = newLevel > before.level;
  if (leveledUp) {
    await setProfileLevel(env.DB, user.id, newLevel);
  }

  return json({
    xp_gained: xp,
    coins_gained: coins,
    leveled_up: leveledUp,
    profile: { ...after, level: newLevel, rank: rankForLevel(newLevel) },
  });
}

async function handleLeaderboard(request, env) {
  const url = new URL(request.url);
  const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get("limit") || "20", 10)));
  const rows = await topByScore(env.DB, limit);
  return json({
    entries: rows.map((row, index) => ({
      rank_position: index + 1,
      username: row.username,
      level: row.level,
      rank: rankForLevel(row.level),
      best_score: row.best_score,
      total_score: row.total_score,
      missions_completed: row.missions_completed,
    })),
  });
}

// -------------------------------------------------------------------- main

const ROUTES = [
  ["POST", "/auth/signup", handleSignup],
  ["POST", "/auth/login", handleLogin],
  ["POST", "/auth/github/complete", handleGithubComplete],
  ["POST", "/auth/google/device/start", handleGoogleDeviceStart],
  ["POST", "/auth/google/device/poll", handleGoogleDevicePoll],
  ["GET", "/me", handleMe],
  ["POST", "/score", handleScore],
  ["GET", "/leaderboard", handleLeaderboard],
];

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    for (const [method, path, handler] of ROUTES) {
      if (request.method === method && url.pathname === path) {
        try {
          return await handler(request, env);
        } catch (err) {
          return json({ error: "Internal error", detail: String(err) }, 500);
        }
      }
    }
    return json({ error: "Not found" }, 404);
  },
};
