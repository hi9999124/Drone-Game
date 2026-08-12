-- Drone / PVO backend schema (Cloudflare D1 / SQLite).
--
-- Design notes:
-- * The game is offline-first -- an account is optional. Signing in only
--   adds server-side sync (coins/XP/level/leaderboard); local play and
--   local saves work exactly as before with no account at all.
-- * password_hash is NULL for accounts created via GitHub/Google only.
-- * github_id / google_sub are nullable + unique, so one account can (in
--   principle) be linked to multiple identity providers later without a
--   schema change.

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  email TEXT,
  password_hash TEXT,
  github_id TEXT UNIQUE,
  google_sub TEXT UNIQUE,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  coins INTEGER NOT NULL DEFAULT 0,
  xp INTEGER NOT NULL DEFAULT 0,
  level INTEGER NOT NULL DEFAULT 1,
  best_score INTEGER NOT NULL DEFAULT 0,
  total_score INTEGER NOT NULL DEFAULT 0,
  missions_completed INTEGER NOT NULL DEFAULT 0,
  targets_destroyed INTEGER NOT NULL DEFAULT 0,
  enemies_destroyed INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_profiles_best_score ON profiles(best_score DESC);
CREATE INDEX IF NOT EXISTS idx_profiles_total_score ON profiles(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
