// D1 query helpers. Kept as plain functions over the `DB` binding rather
// than a class/ORM -- D1's API is already a thin, synchronous-feeling
// wrapper and a hand-rolled ORM would just add a layer to keep in sync with
// schema.sql for no real benefit at this size.

export async function getUserByUsername(db, username) {
  return db.prepare("SELECT * FROM users WHERE username = ?").bind(username).first();
}

export async function getUserByGithubId(db, githubId) {
  return db.prepare("SELECT * FROM users WHERE github_id = ?").bind(githubId).first();
}

export async function getUserByGoogleSub(db, googleSub) {
  return db.prepare("SELECT * FROM users WHERE google_sub = ?").bind(googleSub).first();
}

export async function getUserById(db, id) {
  return db.prepare("SELECT * FROM users WHERE id = ?").bind(id).first();
}

export async function createUser(db, { username, email, passwordHash, githubId, googleSub }) {
  const now = Date.now();
  const result = await db
    .prepare(
      `INSERT INTO users (username, email, password_hash, github_id, google_sub, created_at)
       VALUES (?, ?, ?, ?, ?, ?)`
    )
    .bind(username, email ?? null, passwordHash ?? null, githubId ?? null, googleSub ?? null, now)
    .run();
  const userId = result.meta.last_row_id;
  await db.prepare(`INSERT INTO profiles (user_id, updated_at) VALUES (?, ?)`).bind(userId, now).run();
  return userId;
}

export async function getProfile(db, userId) {
  return db.prepare("SELECT * FROM profiles WHERE user_id = ?").bind(userId).first();
}

export async function createSession(db, userId, token, expiresAt) {
  await db
    .prepare(`INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)`)
    .bind(token, userId, Date.now(), expiresAt)
    .run();
}

export async function getSession(db, token) {
  return db
    .prepare(`SELECT * FROM sessions WHERE token = ? AND expires_at > ?`)
    .bind(token, Date.now())
    .first();
}

export async function applyMissionResult(db, userId, { xpGained, coinsGained, score, won, targetsDestroyed, enemiesDestroyed }) {
  const now = Date.now();
  await db
    .prepare(
      `UPDATE profiles SET
         coins = coins + ?,
         xp = xp + ?,
         best_score = MAX(best_score, ?),
         total_score = total_score + ?,
         missions_completed = missions_completed + ?,
         targets_destroyed = targets_destroyed + ?,
         enemies_destroyed = enemies_destroyed + ?,
         updated_at = ?
       WHERE user_id = ?`
    )
    .bind(coinsGained, xpGained, score, score, won ? 1 : 0, targetsDestroyed, enemiesDestroyed, now, userId)
    .run();
  return getProfile(db, userId);
}

export async function setProfileLevel(db, userId, level) {
  await db.prepare(`UPDATE profiles SET level = ? WHERE user_id = ?`).bind(level, userId).run();
}

export async function topByScore(db, limit) {
  const { results } = await db
    .prepare(
      `SELECT u.username, p.level, p.best_score, p.total_score, p.missions_completed
       FROM profiles p JOIN users u ON u.id = p.user_id
       ORDER BY p.total_score DESC
       LIMIT ?`
    )
    .bind(limit)
    .all();
  return results;
}
