# Saltbox Media Server Stack

Custom Docker services for the R730 Saltbox media server (`192.168.2.103`).

## Architecture

The R730 runs two isolated Docker stacks:

| Stack | Network | Purpose |
|-------|---------|---------|
| **AI Lab** | `ai_lab_net` | Ollama, Open-WebUI, Hive UI, monitoring |
| **Saltbox** | `saltbox` | Media services, cloud storage, game library |

### Saltbox-managed services (via `sb install <role>`)
- Plex / Jellyfin (media streaming)
- Sonarr / Radarr / Prowlarr (media automation)
- Overseerr (request management)
- qBittorrent (downloads)
- Traefik (reverse proxy — shared entry point for both stacks)

### Custom services (this compose file)
- **Seafile** — Self-hosted cloud storage & file sync
- **Romm** — ROM manager with in-browser emulation via EmulatorJS

## Setup

1. Copy the example environment file and fill in your secrets:
   ```bash
   cd /home/misterobots/Home_AI_Lab/services/saltbox
   cp .env.example .env
   nano .env
   ```

2. Ensure the `saltbox` Docker network exists:
   ```bash
   docker network ls | grep saltbox
   # If not present (Saltbox should have created it):
   docker network create saltbox
   ```

3. Start the services:
   ```bash
   docker compose up -d
   ```

4. Access:
   - **Seafile**: `https://seafile.shivelymedia.com` (or `http://192.168.2.103:8082`)
   - **Romm**: `https://romm.shivelymedia.com` (or `http://192.168.2.103:8083`)

## Romm — Game Library

Romm scans your ROM library and enriches it with metadata from IGDB, Screenscraper, and SteamGridDB. Games can be played directly in the browser via EmulatorJS.

### Folder structure
```
/mnt/storage/roms/
├── gba/
│   ├── Pokemon Emerald.gba
│   └── Metroid Fusion.gba
├── snes/
│   ├── Super Metroid.sfc
│   └── Chrono Trigger.sfc
├── n64/
│   └── Zelda - Ocarina of Time.z64
└── ps1/
    └── Final Fantasy VII/
        ├── Final Fantasy VII (Disc 1).bin
        └── Final Fantasy VII (Disc 1).cue
```

See [Romm folder structure docs](https://docs.romm.app/latest/Getting-Started/Folder-Structure/) for supported platforms and naming conventions.

## Seafile — Cloud Storage

Seafile provides Dropbox-like file sync with:
- Desktop sync clients (Windows, macOS, Linux)
- Mobile apps (iOS, Android)
- Client-side encryption support
- WebDAV access
- Online Markdown editing

## GPU Sharing

- **Ollama** (AI Lab): Uses NVIDIA RTX GPU for LLM inference
- **Jellyfin** (Saltbox): Uses Intel iGPU for video transcoding
- No GPU contention between stacks
