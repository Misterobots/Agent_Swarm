# GitHub OAuth App Setup — Hive Mind IDE

> **Phase 1C prerequisite.** This document covers creating the GitHub OAuth App, generating the encryption key, wiring both into the deployment, and fully recreating everything from scratch if needed.

---

## Part 1 — Create the GitHub OAuth App

### Step 1 — Open Developer Settings

1. Sign in to **github.com** as the account that owns or administers the Hive Mind integration.
2. Click your avatar (top-right) → **Settings**.
3. Scroll to the bottom of the left sidebar → **Developer settings**.
4. Click **OAuth Apps** in the left sidebar.
5. Click **New OAuth App** (top-right of the page).

---

### Step 2 — Fill in the Application Form

| Field | Value |
|---|---|
| **Application name** | `Hive Mind IDE` |
| **Homepage URL** | `https://hive.shivelymedia.com` |
| **Application description** | *(optional)* `GitHub Models access for Hive Mind developer IDE` |
| **Authorization callback URL** | `https://hive.shivelymedia.com/api/backend/api/v1/github/callback` |

> **Note on callback URL:** Device Flow never redirects to this URL. GitHub requires the field to be non-empty and a valid HTTPS URL. The value above is safe even though the route does not exist.

---

### Step 3 — Enable Device Flow

Scroll down to the section labelled **"Device Flow"**.  
Check the box: **"Enable Device Flow"**.

> This is the critical step. Without it the `/device/code` endpoint returns a `400` error and the connect flow will fail silently.

---

### Step 4 — Register and Copy the Client ID

1. Click **Register application**.
2. You land on the app's detail page.
3. Copy the **Client ID** — it looks like `Ov23li...` (20 alphanumeric chars).
4. **Do NOT generate a Client Secret** — Device Flow does not use one.

---

### Step 5 — Wire the Client ID into the Deployment

On **Justin-PC** (192.168.2.101), open `/workspace/network.env` (the repo root `network.env` mounted into containers):

```ini
# === GitHub OAuth (Phase 1C) ===
GITHUB_OAUTH_CLIENT_ID=Ov23liXXXXXXXXXXXXXX   # ← paste Client ID here
TOKEN_ENCRYPTION_KEY=<see Part 2 below>
```

---

## Part 2 — Generate the Fernet Encryption Key

Tokens are stored **encrypted at rest** in PostgreSQL using symmetric Fernet encryption. The key must be generated once and stored in `network.env`.

### Generate the key (run once)

On any machine with Python 3 and the `cryptography` package:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Example output:
```
uLdrFPYjSR3vHKJ2dO4aWt1ZeBm9NcGxQk0pVnIqRsE=
```

Copy the full 44-character base64 string into `network.env`:

```ini
TOKEN_ENCRYPTION_KEY=uLdrFPYjSR3vHKJ2dO4aWt1ZeBm9NcGxQk0pVnIqRsE=
```

> **CRITICAL — Key permanence:** If this key is changed or lost, all stored GitHub tokens become unreadable. Users will need to re-authenticate via the Device Flow. The key itself is never stored in the database.

---

## Part 3 — Restart the Backend

After saving `network.env`, restart the `agent_runtime` container on Justin-PC to pick up the new env vars:

```bash
ssh misterobots@192.168.2.101
cd /workspace/execution_plane
docker compose restart agent_runtime
```

Verify the vars loaded:

```bash
docker exec agent_runtime env | grep -E "GITHUB_OAUTH|TOKEN_ENC"
```

Both variables should appear with their values.

---

## Part 4 — First Use / Smoke Test

1. Navigate to `https://hive.shivelymedia.com/settings`.
2. Under **Connected Accounts**, click **Connect GitHub Models**.
3. A panel appears showing an 8-character code (e.g., `AB12-CD34`) and an **Open GitHub** link.
4. Click the link (or go to `https://github.com/login/device`), enter the code, and click **Authorize**.
5. The UI polls every 5 seconds. Within ~10 seconds the panel changes to:  
   `Connected as @your-github-username`
6. Navigate to `/dev` or the chat — the model selector now shows a **GitHub Models** group with GPT-4o, Claude Sonnet 4, Gemini 2.0 Flash, Llama 4, and more.

---

## Part 5 — Emergency Restoration Runbook

Use this section to recreate the entire GitHub OAuth integration from zero (e.g., after a stolen key, deleted OAuth app, or full cluster rebuild).

### Checklist

- [ ] Create new OAuth App on GitHub (Part 1)
- [ ] Copy new Client ID
- [ ] Generate new Fernet key (Part 2)
- [ ] Update `network.env` on Justin-PC
- [ ] Restart `agent_runtime` container
- [ ] Optionally: clear old tokens from DB (if key changed)
- [ ] Smoke test

---

### Step R1 — Revoke / Delete the Old OAuth App (if compromised)

```
github.com → Settings → Developer settings → OAuth Apps → Hive Mind IDE → Delete application
```

**Warning:** This immediately invalidates all access tokens issued under the old app. All users lose GitHub Models access until they reconnect.

---

### Step R2 — Create a New OAuth App

Repeat **Part 1** exactly. The new Client ID will be a different string.

---

### Step R3 — Rotate the Encryption Key (if key was compromised)

1. Generate a new Fernet key (Part 2).
2. **All stored tokens are now unreadable.** Clear them from the database before rotating:

```bash
ssh misterobots@192.168.2.102
psql -U langfuse -d langfuse -c "TRUNCATE swarm.github_oauth_tokens;"
```

3. Update `network.env` with the new key and new Client ID.
4. Restart `agent_runtime`.
5. Notify users they must reconnect their GitHub account.

> If the key was NOT compromised (e.g., you're just replacing a lost app), you can skip the DB truncate and keep existing tokens — they're already encrypted under the current key.

---

### Step R4 — Verify DB Schema Exists

The table is auto-created by `agents/github_oauth.py` on first use. To verify manually:

```bash
ssh misterobots@192.168.2.102
psql -U langfuse -d langfuse -c "\d swarm.github_oauth_tokens"
```

Expected columns:

```
 Column          | Type
-----------------+-----------------------------
 user_id         | text  (Authentik UID — PK)
 github_username | text
 access_token    | bytea (Fernet-encrypted)
 scopes          | text
 created_at      | timestamp with time zone
 updated_at      | timestamp with time zone
```

If the table is missing, it will be auto-created on the next connection attempt. To force-create it manually:

```bash
docker exec agent_runtime python3 -c "from github_oauth import _get_conn; _get_conn().close(); print('Table OK')"
```

---

### Step R5 — Verify Backend Endpoints

```bash
# From any node on the LAN
curl -s http://192.168.2.101:8008/api/v1/github/status \
  -H "X-authentik-uid: test-uid-1234" | python3 -m json.tool
```

Expected response (no token stored):
```json
{
  "connected": false,
  "github_username": null
}
```

---

### Step R6 — Re-deploy UI (if settings page was lost)

The GitHub connect UI lives in:
- `ui/src/components/settings/github-connect.tsx` — Device Flow component
- `ui/src/app/settings/page.tsx` — Connected Accounts section (imports `GitHubConnect`)

Both are committed in the repo at tag `checkpoint-phase1d`. To restore:

```bash
git checkout checkpoint-phase1d -- ui/src/components/settings/github-connect.tsx
git checkout checkpoint-phase1d -- ui/src/app/settings/page.tsx
```

Then rebuild and redeploy `hive_ui` on R730:

```bash
ssh misterobots@192.168.2.103
cd /workspace
docker compose -f r730_gateway/docker-compose.yml up -d --build hive-ui
```

---

### Step R7 — Re-deploy Backend (if provider code was lost)

Backend files committed at `checkpoint-phase1c`:
- `agents/github_oauth.py`
- `agents/providers/github_models_provider.py`
- `agents/main.py` (contains device flow endpoints + model router)
- `agents/config.py` (contains `GITHUB_OAUTH_CLIENT_ID` + `TOKEN_ENCRYPTION_KEY`)

To restore:

```bash
git checkout checkpoint-phase1c -- agents/github_oauth.py \
  agents/providers/github_models_provider.py \
  agents/main.py \
  agents/config.py
```

Then rebuild `agent_runtime`:

```bash
ssh misterobots@192.168.2.101
cd /workspace/execution_plane
docker compose up -d --build agent_runtime
```

---

## Part 6 — Architecture Reference

```
User Browser
    │
    ├─ POST /api/backend/api/v1/github/device-authorize
    │       → backend calls POST https://github.com/login/device/code
    │       ← returns { user_code: "AB12-CD34", verification_uri, device_code, interval }
    │
    ├─ User visits github.com/login/device, enters code
    │
    ├─ POST /api/backend/api/v1/github/device-poll  (every ~5s)
    │       → backend polls POST https://github.com/login/oauth/access_token
    │       → on success: GET https://api.github.com/user (get username)
    │       → store Fernet-encrypted token in swarm.github_oauth_tokens
    │       ← returns { connected: true, github_username: "..." }
    │
    └─ All subsequent model calls: model ID starts with "github/"
           → /v1/chat/completions routes to GitHubModelsProvider
           → provider calls https://models.github.ai/inference/chat/completions
               with Authorization: Bearer <decrypted token>
```

### GitHub Models API endpoint

```
POST https://models.github.ai/inference/chat/completions
Authorization: Bearer <github_token>
Content-Type: application/json

{
  "model": "gpt-4o",           ← strip "github/" prefix from internal ID
  "messages": [...],
  "stream": true
}
```

---

## Part 7 — Quick Reference

| Item | Value / Location |
|---|---|
| GitHub OAuth App URL | `github.com/settings/developers` |
| App name | `Hive Mind IDE` |
| Device Flow enable | Checkbox on app settings page |
| Client ID env var | `GITHUB_OAUTH_CLIENT_ID` in `network.env` |
| Encryption key env var | `TOKEN_ENCRYPTION_KEY` in `network.env` |
| `network.env` location | `/workspace/network.env` (Justin-PC) |
| DB table | `swarm.github_oauth_tokens` in `langfuse` DB on 192.168.2.102 |
| Phase 1C tag | `checkpoint-phase1c` |
| Phase 1D tag | `checkpoint-phase1d` |
| Backend container | `agent_runtime` on Justin-PC (192.168.2.101) |
| UI container | `hive-ui` on R730 (192.168.2.103) |

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `network.env` | Configuration | OAuth env vars (GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET) |
| `agents/github_oauth.py` | Implementation | OAuth callback handler |
| `swarm.github_oauth_tokens` | Database | Token storage table (in `langfuse` DB) |
| [GitHub OAuth Apps](https://docs.github.com/en/apps/oauth-apps) | External | OAuth App documentation |

</details>

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-01 | AI-Copilot | Initial GitHub OAuth setup guide |

</details>

---

## Maintenance & Update Guide

- Rotate `GITHUB_CLIENT_SECRET` annually or upon suspicion of compromise.
- Update callback URLs if the R730 IP or domain changes.
- Update the DB table schema if additional OAuth scopes are needed.

---

## Functionality Testing

| Step | Expected Result |
|------|----------------|
| Click "Sign in with GitHub" in Hive UI | Redirects to GitHub authorization page |
| Authorize the app | Callback returns to Hive UI, user session created |
| Check DB | `SELECT * FROM swarm.github_oauth_tokens` shows new row |
