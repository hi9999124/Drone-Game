# Drone / PVO backend

Cloudflare Worker + D1 database: accounts (username/password, GitHub, Google),
coins/XP/levels/ranks, and a leaderboard. $0 on Cloudflare's free tier for a
project this size.

The game works fully offline with no account at all -- this backend only adds
optional cross-device sync and the online leaderboard. Every endpoint here was
tested locally against a real (local) D1 database before being written up
below; nothing here is unverified.

There are two ways to deploy this: the CLI (`wrangler`, needs Node.js
installed locally) or the Cloudflare dashboard alone (no installs, just
paste things into the browser). Pick one:

- **CLI** — see "One-time setup" below. Handles both the database and the
  Worker code, and is what `backend/README.md`'s later sections (GitHub/
  Google secrets) assume.
- **Dashboard only** — see "Dashboard-only setup" further down. Everything
  is copy-paste into the Cloudflare web console; no terminal needed at all.
  Slightly more manual for the D1 binding step, and Google sign-in's secret
  still needs one CLI-free equivalent (also covered there).

## One-time setup

You need a Cloudflare account (free) and Node.js installed locally.

```bash
cd backend
npm install
npx wrangler login          # opens a browser to authorize the CLI
```

### 1. Create the D1 database

```bash
npx wrangler d1 create dronepvo
```

This prints a `database_id`. Open `backend/wrangler.toml` and replace
`REPLACE_WITH_YOUR_D1_DATABASE_ID` with that value.

### 2. Apply the schema

```bash
npm run db:migrate:remote
```

(`npm run db:migrate:local` does the same against a local SQLite file, useful
if you want to run `npm run dev` and test against `http://localhost:8787`
first without touching the real database.)

### 3. Deploy the Worker

```bash
npm run deploy
```

Wrangler prints the Worker's URL, something like
`https://dronepvo-backend.<your-subdomain>.workers.dev`. **Copy this URL** --
it goes into the game client next (see "Wire up the game client" below).

At this point username/password sign-up, login, coins/XP/levels, and the
leaderboard are fully live. GitHub and Google sign-in need one more step each.

## Dashboard-only setup (no CLI)

Everything here happens at <https://dash.cloudflare.com> in the browser.

### 1. Create the database

**Storage & Databases -> D1 SQL Database -> Create Database.** Name it
`dronepvo`, create it.

### 2. Create the tables

Open the new database, go to its **Console** tab, and paste this in and run
it (this is the exact contents of `backend/schema.sql` -- nothing to edit):

```sql
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
```

You should see three tables appear (`users`, `profiles`, `sessions`) in that
same tab's schema browser once it runs.

### 3. Create the Worker and paste in the code

**Compute (Workers & Pages) -> Create -> Workers -> deploy a "Hello World"
starter** (any starting template is fine, you're about to replace it). Name
it `dronepvo-backend`, create it, then **Edit code** (the in-browser editor).

The actual Worker is written as several source files with imports between
them (`backend/src/`), which the browser editor can't run directly -- so
instead, replace the editor's contents with the single bundled file below,
which is the same code with everything inlined into one file. It's generated
from source with `npm run bundle` (`backend/dist/worker-bundled.js`,
git-ignored since it's just a build output) and produces byte-identical
behavior to the multi-file version -- verified by running the actual
signup/leaderboard/404 checks against it locally before writing this.

*(The bundled file's full contents were sent alongside this message -- open
it, select all, copy, and paste over everything in the editor.)*

Click **Deploy**. Cloudflare shows you the Worker's URL, something like
`https://dronepvo-backend.<your-subdomain>.workers.dev` -- copy it for the
"Wire up the game client" step below.

### 4. Attach the D1 database to the Worker

Back on the Worker's page: **Settings -> Bindings -> Add -> D1 Database.**
- **Variable name**: `DB` (must be exactly this -- the code reads
  `env.DB`)
- **D1 database**: the `dronepvo` database from step 1

Save, and it'll prompt to redeploy -- confirm that.

At this point you're at the same place the CLI path reaches after its step
3: username/password auth, coins/XP/levels, and the leaderboard are live.
GitHub sign-in setup below is identical either way. For Google (needs a
secret, which the CLI path sets via `wrangler secret put`), the dashboard
equivalent is the same **Settings -> Bindings** page: **Add -> Secret**,
name `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`, paste the values from the
Google setup below, save, redeploy.

## GitHub sign-in setup

1. Go to <https://github.com/settings/developers> -> **OAuth Apps** -> **New
   OAuth App**.
2. Fill in:
   - **Application name**: `Drone / PVO` (anything you like)
   - **Homepage URL**: `https://github.com/hi9999124/Drone-Game`
   - **Authorization callback URL**: same homepage URL -- it's a required
     field but unused by the device flow the game actually uses.
3. Click **Register application**.
4. On the app's settings page, check **"Enable Device Flow"** (unchecked by
   default) and save.
5. Copy the **Client ID** shown on that page.

That Client ID is *public* (device flow needs no client secret) -- put it
directly in the game client, see "Wire up the game client" below. Nothing
needs to be pasted into the Cloudflare console for GitHub.

## Google sign-in setup

Google's device flow needs a client secret, which must stay server-side, so
this one has an extra step to store it in Cloudflare.

1. Go to <https://console.cloud.google.com/> and create (or pick) a project.
2. **APIs & Services -> OAuth consent screen**: set it up if you haven't
   already (User type: External; fill in an app name and your email; you can
   leave it in "Testing" status, which is fine for a hobby project -- add
   yourself and any friends as test users there while it's in that mode).
3. **APIs & Services -> Credentials -> Create Credentials -> OAuth client
   ID**.
4. **Application type: "TVs and Limited Input devices"** -- this is the type
   that supports the device flow the game uses.
5. Give it a name, click **Create**. Copy the **Client ID** and **Client
   Secret** shown.
6. Back in your terminal:

   ```bash
   cd backend
   npx wrangler secret put GOOGLE_CLIENT_ID
   # paste the Client ID when prompted, press enter

   npx wrangler secret put GOOGLE_CLIENT_SECRET
   # paste the Client Secret when prompted, press enter
   ```

7. Re-deploy so the Worker picks up the new secrets:

   ```bash
   npm run deploy
   ```

## Wire up the game client

Open `src/backend.py` in the main game repo and set:

```python
API_BASE = "https://dronepvo-backend.<your-subdomain>.workers.dev"  # from step 3 above
GITHUB_CLIENT_ID = "..."  # from the GitHub setup above
```

Google needs no client-side config -- the game only ever talks to your
Worker for Google sign-in, never to Google directly, since the secret lives
on the Worker.

## API reference

All bodies/responses are JSON. Authenticated endpoints take
`Authorization: Bearer <token>`.

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/auth/signup` | `{username, password}` | username: 3-20 chars, letters/digits/underscore. password: 8+ chars. |
| POST | `/auth/login` | `{username, password}` | |
| POST | `/auth/github/complete` | `{access_token}` | Client already ran GitHub's device flow itself; this verifies the token and creates/logs in the account. |
| POST | `/auth/google/device/start` | `{}` | Returns `{device_code, user_code, verification_url, interval, expires_in}` from Google. |
| POST | `/auth/google/device/poll` | `{device_code}` | Poll on the returned `interval`. Returns `{status: "pending"}` while waiting, or `{status: "ok", token, profile}` once approved. |
| GET | `/me` | | Current user + profile. |
| POST | `/score` | `{score, won, targets_destroyed, enemies_destroyed}` | Adds XP/coins, recomputes level, returns `{xp_gained, coins_gained, leveled_up, profile}`. |
| GET | `/leaderboard?limit=20` | | Top players by total score. |

## Leveling formula

XP needed to go from level `L` to `L+1` is `50*L`. Mirrored exactly in both
`backend/src/levels.js` (server) and `src/leveling.py` (client, for fully
offline play) so online/offline totals never disagree once synced.

| Level range | Rank |
|---|---|
| 1-4 | Rookie |
| 5-9 | Cadet |
| 10-19 | Veteran |
| 20-29 | Ace |
| 30+ | Legend |

Coins/XP per mission: `xp = score`, `coins = floor(score / 20)`.

## Local development

```bash
npm run dev                    # runs the Worker on http://localhost:8787
                                # against a LOCAL sqlite copy of D1, not production
npm run db:migrate:local       # apply schema.sql to that local copy
```
