# Mission Control

Mission Control is a cooperative smart-home challenge game for kids that runs against your Home Assistant instance.

## What this add-on does

- Hosts the Mission Control web UI inside Home Assistant
- Talks to Home Assistant over its normal REST and WebSocket APIs
- Stores challenge data, generated audio, and cached images in the add-on data directory
- Exposes a LAN web UI on port `8765` so Home Assistant speakers and browsers can fetch generated media

## Required options

- `ha_url`: Your Home Assistant URL. Default is `http://192.168.2.100:8123`
- `ha_token`: A dedicated long-lived Home Assistant access token
- `gemini_api_key`: Gemini API key for TTS, challenge generation, and images
- `server_url`: LAN-reachable Mission Control URL. Default is `http://192.168.2.100:8765`

`server_url` must stay reachable from other devices on your LAN. Do not set it to an ingress-only URL.

## First run

1. Open the add-on and set the required options.
2. Start the add-on.
3. Open the web UI.
4. Discover speakers and confirm safe devices only.
5. Generate a small challenge set and run a smoke test.

## Notes

- Mission Control is intentionally separate from Hive.
- This wrapper persists add-on options into Mission Control's own `config.json` on startup so add-on settings override stale saved values.