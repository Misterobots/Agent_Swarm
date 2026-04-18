#!/usr/bin/env sh
set -eu

echo "=== Mission Control Home Assistant Add-on ==="

mkdir -p /data

if [ -e /app/data ] && [ ! -L /app/data ]; then
  rm -rf /app/data
fi

if [ ! -e /app/data ]; then
  ln -s /data /app/data
fi

python3 - <<'PY'
import json
import os
from pathlib import Path

data_dir = Path("/data")
options_path = data_dir / "options.json"
config_path = data_dir / "config.json"

options = {}
if options_path.exists():
    options = json.loads(options_path.read_text(encoding="utf-8"))

config = {}
if config_path.exists():
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        config = {}

mapping = {
    "ha_url": "HA_URL",
    "ha_token": "HA_TOKEN",
    "gemini_api_key": "GEMINI_API_KEY",
    "server_url": "SERVER_URL",
}

for key, env_name in mapping.items():
    value = options.get(key)
    if value not in (None, ""):
        config[key] = value
        os.environ[env_name] = value

config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

print("Persisted add-on options into /data/config.json")
for key in mapping:
    print(f"  {key}: {'set' if config.get(key) else 'unset'}")
PY

exec uvicorn server:app --host 0.0.0.0 --port 8765