# Mission Control Native Home Assistant Add-on

This runbook packages Mission Control as a native Home Assistant add-on for the Home Assistant box at `192.168.2.100`.

Mission Control is **not** part of Hive or the R730 Saltbox stack yet. Keep it isolated on the Home Assistant box for now.

---

## Current Status

- Home Assistant UI is reachable at `http://192.168.2.100:8123`.
- The native add-on scaffold is prepared locally under `services/home_assistant/addons/mission-control/`.
- The SSH deploy helper is prepared locally at `scripts/deploy_mission_control_home_assistant.sh`.
- From this workspace, SSH to `misterobots@192.168.2.100` is still refusing connections on the tested ports, so the helper cannot be executed yet from here.

---

## Add-on Bundle

Files:

- `services/home_assistant/addons/mission-control/config.yaml`
- `services/home_assistant/addons/mission-control/Dockerfile`
- `services/home_assistant/addons/mission-control/run.sh`
- `services/home_assistant/addons/mission-control/DOCS.md`
- `services/home_assistant/addons/mission-control/translations/en.yaml`

Required add-on options:

- `ha_url=http://192.168.2.100:8123`
- `ha_token=<dedicated long-lived Home Assistant token>`
- `gemini_api_key=<Gemini API key>`
- `server_url=http://192.168.2.100:8765`

`server_url` must remain LAN-reachable so browsers and Home Assistant media playback can fetch generated audio correctly.

---

## Option 1: Copy into `/addons/local` After Enabling SSH

Once SSH is enabled on the Home Assistant host, run:

```bash
bash scripts/deploy_mission_control_home_assistant.sh
```

This helper will:

1. Verify SSH access to `misterobots@192.168.2.100`
2. Copy the add-on scaffold to `/addons/local/mission_control`
3. Ask Home Assistant to reload add-ons if the `ha` CLI exists
4. Leave installation and option entry to the Home Assistant UI

---

## Option 2: Install Manually via Home Assistant Local Add-ons

If you have Samba, terminal, or add-on shell access on the Home Assistant box:

```bash
mkdir -p /addons/local/mission_control
```

Copy the contents of `services/home_assistant/addons/mission-control/` into:

- `/addons/local/mission_control/`

Then in Home Assistant:

1. Open `Settings -> Add-ons -> Add-on Store`
2. Open the three-dot menu and choose `Check for updates`
3. Open the local `Mission Control` add-on
4. Enter the add-on options
5. Install and start the add-on

---

## First-Run Validation

After the add-on starts:

1. Open `http://192.168.2.100:8765`
2. Or open the add-on via the Home Assistant sidebar ingress entry
3. Verify Home Assistant URL and token in the Settings page
4. Add the Gemini API key
5. Discover `media_player` entities
6. Select only safe speakers and devices for the first test
7. Generate challenges and run a small LAN-only smoke test

---

## Validation Commands

From another machine on the LAN:

```bash
curl http://192.168.2.100:8765
curl -H "Authorization: Bearer <HA_TOKEN>" http://192.168.2.100:8123/api/
```

---

## Source References

| Source | Type | Relevance |
|--------|------|----------|
| `services/home_assistant/addons/mission-control/config.yaml` | Add-on manifest | Canonical Home Assistant add-on definition |
| `services/home_assistant/addons/mission-control/Dockerfile` | Add-on image wrapper | Wraps the upstream Mission Control image |
| `services/home_assistant/addons/mission-control/run.sh` | Startup wrapper | Persists add-on options and starts Mission Control |
| `scripts/deploy_mission_control_home_assistant.sh` | Operations helper | SSH-based copy into `/addons/local/mission_control` |
| `network.env` | Configuration | Canonical Home Assistant IP and URL |
| `agents/config.py` | Configuration | Shared Home Assistant URL assumptions in the repo |
