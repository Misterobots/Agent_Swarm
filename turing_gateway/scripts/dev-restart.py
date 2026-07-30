#!/usr/bin/env python3
"""
dev-restart — silence Uptime Kuma around an INTENTIONAL container restart / maintenance,
so planned work doesn't page you. (Quick restarts are already covered by the ~2-min
retry grace on the monitors; this is for work that runs longer than that.)

It pauses the Kuma monitor(s) for a container, optionally `docker restart`s it, waits
until it's back up, then resumes. With --hold it keeps the monitors paused for a set
window of planned work. Monitors are ALWAYS resumed on exit — normal end, Ctrl-C, or
SIGTERM/SIGHUP (terminal close) — so you can't leave one muted by accident.

Usage:
  dev-restart.py <container> [--hold MIN] [--no-restart]

Examples:
  dev-restart.py jellyfin                       # pause -> docker restart -> wait until up -> resume
  dev-restart.py radarr --hold 20               # restart, then keep paused for 20 min of work
  dev-restart.py sonarr --hold 30 --no-restart  # 30-min maintenance window; you manage the container

Env (same as the seeder):
  KUMA_URL  (default http://localhost:3009)   KUMA_USERNAME   KUMA_PASSWORD

Run with the Turing venv:
  /home/misterobots/.venvs/kuma/bin/python turing_gateway/scripts/dev-restart.py jellyfin
"""
import os
import sys
import time
import signal
import subprocess
import argparse

try:
    from uptime_kuma_api import UptimeKumaApi
except ImportError:
    sys.exit("Missing dep. Use the venv: /home/misterobots/.venvs/kuma/bin/python  "
             "(or: pip install uptime-kuma-api)")

KUMA_URL = os.environ.get("KUMA_URL", "http://localhost:3009")
USER = os.environ.get("KUMA_USERNAME")
PW = os.environ.get("KUMA_PASSWORD")


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser(
        description="Pause Kuma monitors around an intentional container restart/maintenance.")
    ap.add_argument("container", help="container name, e.g. jellyfin")
    ap.add_argument("--hold", type=int, default=0, metavar="MIN",
                    help="keep monitors paused this many minutes (planned work)")
    ap.add_argument("--no-restart", action="store_true",
                    help="don't docker restart; just open a maintenance window")
    a = ap.parse_args()
    if not (USER and PW):
        sys.exit("Set KUMA_USERNAME and KUMA_PASSWORD in the environment.")

    api = UptimeKumaApi(KUMA_URL)
    api.login(USER, PW)

    c = a.container
    targets = [m for m in api.get_monitors()
               if m["name"] in (f"[container] {c}", f"[external] {c}")]
    if not targets:
        api.disconnect()
        sys.exit(f"No Kuma monitors matched '{c}' "
                 f"(looked for '[container] {c}' and '[external] {c}').")
    ids = [m["id"] for m in targets]
    names = ", ".join(m["name"] for m in targets)

    state = {"resumed": False}

    def resume(*_):
        if state["resumed"]:
            return
        for i in ids:
            try:
                api.resume_monitor(i)
            except Exception as e:  # noqa: BLE001
                print(f"  ! resume failed for monitor {i}: {e}")
        state["resumed"] = True
        print(f"resumed: {names}")

    # Resume on terminal close / kill too, not just clean exit or Ctrl-C.
    for sig in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), lambda *_: (resume(), sys.exit(0)))

    print(f"pausing: {names}")
    for i in ids:
        api.pause_monitor(i)

    try:
        if not a.no_restart:
            print(f"docker restart {c} ...")
            r = docker("restart", c)
            print("  " + (r.stdout.strip() or r.stderr.strip() or "(no output)"))
            fmt = "{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
            for _ in range(60):  # up to ~2 min for running (+healthy if it has a healthcheck)
                st = docker("inspect", "-f", fmt, c).stdout.split()
                if st and st[0] == "true" and (len(st) < 2 or st[1] in ("healthy", "none")):
                    print("  container is up")
                    break
                time.sleep(2)
        if a.hold > 0:
            print(f"holding monitors paused for {a.hold} min (Ctrl-C to resume early)...")
            time.sleep(a.hold * 60)
    finally:
        resume()
        try:
            api.disconnect()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
