#!/usr/bin/env python3
"""
Seed Uptime Kuma with the Media Dashboard monitor set (Phase 1 of
docs/media_dashboard_plan.md).

Creates, idempotently and fault-tolerantly (every step is independent — one
failure never aborts the rest, and each prints its own result):
  * a Docker Host pointing at Turing's read-only docker-socket-proxy
  * one Docker-container monitor per critical container
  * one HTTP(s) monitor per public *.shivelymedia.com URL
  * an ntfy notification (topic 'saltbox-down') attached to every monitor

Container monitors use interval=60s / maxretries=2 so an *intentional* dev restart
(back within ~2 min) does NOT alert, while a real death does.

────────────────────────────────────────────────────────────────────────────
PREREQUISITES
  1. Create the Kuma admin account first at  http://192.168.2.103:3009
  2. pip install uptime-kuma-api
  3. Export credentials (nothing hardcoded — your password never touches git):

     export KUMA_URL="http://192.168.2.103:3009"
     export KUMA_USERNAME="<admin user>"
     export KUMA_PASSWORD="<admin password>"
     export KUMA_NTFY_TOKEN="tk_xxxxxxxxxxxxxxxx"   # the ntfy write token for saltbox-down

     # PowerShell:  $env:KUMA_URL="..."   etc.
  4. python seed_kuma_monitors.py

Re-running is safe: existing host/notification/monitors (matched by name) are skipped.
Paste the full output if anything says FAIL — the per-step errors pin down the cause.
────────────────────────────────────────────────────────────────────────────
"""
import os
import sys

try:
    import uptime_kuma_api
    from uptime_kuma_api import UptimeKumaApi, MonitorType, NotificationType
except ImportError:
    sys.exit("Missing dependency. Run:  pip install uptime-kuma-api")

# DockerType enum is preferred by newer lib versions; fall back to plain string.
try:
    from uptime_kuma_api import DockerType
    DOCKER_TYPE_TCP = DockerType.TCP
except Exception:  # noqa: BLE001
    DOCKER_TYPE_TCP = "tcp"

# ── config ───────────────────────────────────────────────────────────────────
KUMA_URL   = os.environ.get("KUMA_URL", "http://192.168.2.103:3009")
USERNAME   = os.environ.get("KUMA_USERNAME")
PASSWORD   = os.environ.get("KUMA_PASSWORD")
NTFY_TOKEN = os.environ.get("KUMA_NTFY_TOKEN")

NTFY_URL      = os.environ.get("KUMA_NTFY_URL", "http://ntfy-Turing:80")  # Kuma's view (ai_lab_net)
NTFY_TOPIC    = "saltbox-down"
NTFY_PRIORITY = 4

DOCKER_HOST_NAME  = "turing-socket-proxy"
DOCKER_DAEMON_URL = "http://docker-socket-proxy-turing:2375"

INTERVAL, MAX_RETRY, RETRY_INT = 60, 2, 60

CONTAINERS = {
    "Saltbox / edge": [
        "traefik", "cloudflared", "authentik", "authentik-worker", "authentik-postgres",
        "jellyfin", "radarr", "sonarr", "sabnzbd", "seerr", "overseerr", "aha-site",
    ],
    "AI / Memex core": ["agent_runtime", "memex_ui", "ollama-turing", "redis-turing"],
    "Monitoring self-watch": [
        "prometheus-turing", "alertmanager-turing", "cadvisor-turing",
        "ntfy-Turing", "hollerith-turing", "loki-turing",
    ],
}

HTTP_URLS = [
    "https://memex.shivelymedia.com",
    "https://jellyfin.shivelymedia.com",
    "https://radarr.shivelymedia.com",
    "https://sonarr.shivelymedia.com",
    "https://sabnzbd.shivelymedia.com",
    "https://seerr.shivelymedia.com",
    "https://dash.shivelymedia.com",
    "https://notify.shivelymedia.com",
]
ACCEPTED_STATUS = ["200-299", "300-399"]


def main():
    if not (USERNAME and PASSWORD):
        sys.exit("Set KUMA_USERNAME and KUMA_PASSWORD (see header).")

    print(f"uptime_kuma_api version: {getattr(uptime_kuma_api, '__version__', '?')}")
    print(f"connecting to {KUMA_URL} ...")
    api = UptimeKumaApi(KUMA_URL)
    try:
        api.login(USERNAME, PASSWORD)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"LOGIN FAILED: {e}\n-> check KUMA_URL / KUMA_USERNAME / KUMA_PASSWORD")
    try:
        print(f"connected. Kuma version: {api.info().get('version','?')}")
    except Exception:  # noqa: BLE001
        print("connected (version unknown)")

    created, skipped, failed = [], [], []

    # 1) notification ----------------------------------------------------------
    notif_id = None
    if not NTFY_TOKEN:
        print("WARNING: KUMA_NTFY_TOKEN not set — creating monitors WITHOUT ntfy. "
              "Set it and re-run, or add the notification in the UI.")
    else:
        try:
            existing = {n["name"]: n["id"] for n in api.get_notifications()}
        except Exception as e:  # noqa: BLE001
            existing = {}
            print(f"(could not list notifications: {e})")
        name = "ntfy — saltbox-down"
        if name in existing:
            notif_id = existing[name]
            print(f"notification exists (id={notif_id})")
        else:
            try:
                res = api.add_notification(
                    name=name, type=NotificationType.NTFY, isDefault=False,
                    ntfyserverurl=NTFY_URL, ntfytopic=NTFY_TOPIC, ntfyPriority=NTFY_PRIORITY,
                    ntfyAuthenticationMethod="accessToken", ntfyaccesstoken=NTFY_TOKEN,
                )
                notif_id = res.get("id") or res.get("notificationID")
                print(f"created notification (id={notif_id})")
            except Exception as e:  # noqa: BLE001
                print(f"FAIL notification: {e}\n-> monitors will still be created; "
                      f"add ntfy manually in Settings→Notifications if this persists.")

    notif_list = {notif_id: True} if notif_id else None

    # 2) docker host -----------------------------------------------------------
    dh_id = None
    try:
        hosts = {h["name"]: h["id"] for h in api.get_docker_hosts()}
    except Exception as e:  # noqa: BLE001
        hosts = {}
        print(f"(could not list docker hosts: {e})")
    if DOCKER_HOST_NAME in hosts:
        dh_id = hosts[DOCKER_HOST_NAME]
        print(f"docker host exists (id={dh_id})")
    else:
        try:
            api.add_docker_host(name=DOCKER_HOST_NAME, dockerType=DOCKER_TYPE_TCP,
                                dockerDaemon=DOCKER_DAEMON_URL)
            dh_id = {h["name"]: h["id"] for h in api.get_docker_hosts()}.get(DOCKER_HOST_NAME)
            print(f"created docker host (id={dh_id})")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL docker host: {e}\n-> container monitors will be SKIPPED "
                  f"(HTTP monitors still created). Fix and re-run.")

    try:
        existing_monitors = {m["name"] for m in api.get_monitors()}
    except Exception:  # noqa: BLE001
        existing_monitors = set()

    def add(name, **kw):
        if name in existing_monitors:
            skipped.append(name)
            return
        try:
            if notif_list:
                kw["notificationIDList"] = notif_list
            api.add_monitor(name=name, interval=INTERVAL, retryInterval=RETRY_INT,
                            maxretries=MAX_RETRY, **kw)
            created.append(name)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{name}: {e}")

    # 3) container monitors (only if the docker host resolved) -----------------
    if dh_id:
        for group, names in CONTAINERS.items():
            for c in names:
                add(f"[container] {c}", type=MonitorType.DOCKER,
                    docker_container=c, docker_host=dh_id)
    else:
        print("skipping container monitors — no docker host id")

    # 4) http monitors ---------------------------------------------------------
    for url in HTTP_URLS:
        label = url.split("//", 1)[-1].split(".")[0]
        add(f"[external] {label}", type=MonitorType.HTTP, url=url,
            accepted_statuscodes=ACCEPTED_STATUS)

    # summary ------------------------------------------------------------------
    print("\n──────── summary ────────")
    print(f"created: {len(created)}")
    for n in created:
        print(f"   + {n}")
    if skipped:
        print(f"skipped (already existed): {len(skipped)}")
    if failed:
        print(f"FAILED: {len(failed)}")
        for f in failed:
            print(f"   ! {f}")
    print("\nDone. Refresh the Kuma dashboard to see green/red status.")
    try:
        api.disconnect()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
