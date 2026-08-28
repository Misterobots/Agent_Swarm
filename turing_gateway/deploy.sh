#!/usr/bin/env bash
# Promote the tracked Turing compose template after a clean git pull.
# Run on Turing from a clean deployment checkout:
#   turing_gateway/deploy.sh [--check] [--no-build]
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
root_dir="/home/misterobots"
template="$repo_dir/turing_gateway/docker-compose.yml"
live="$root_dir/docker-compose.yml"
env_file="/home/network.env"
candidate="$root_dir/docker-compose.yml.candidate"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
check_only=false
build=true

for arg in "$@"; do
  case "$arg" in
    --check) check_only=true ;;
    --no-build) build=false ;;
    -h|--help)
      printf '%s\n' "Usage: turing_gateway/deploy.sh [--check] [--no-build]"
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$arg" >&2
      exit 2
      ;;
  esac
done

for path in "$template" "$env_file"; do
  [[ -f "$path" ]] || { printf 'Required file missing: %s\n' "$path" >&2; exit 1; }
done

if [[ -n "$(git -C "$repo_dir" status --porcelain)" ]]; then
  printf '%s\n' "Refusing to deploy from a dirty checkout: $repo_dir" >&2
  printf '%s\n' "Commit, stash, or use a clean checkout before deploying." >&2
  exit 1
fi

if ! git -C "$repo_dir" diff --quiet HEAD -- turing_gateway/docker-compose.yml; then
  printf '%s\n' "Refusing to deploy uncommitted Compose changes." >&2
  exit 1
fi

cp "$template" "$candidate"
trap 'rm -f "$candidate"' EXIT
docker compose --env-file "$env_file" -f "$candidate" config --quiet

if "$check_only"; then
  printf '%s\n' "Compose validation passed; live compose was not changed."
  exit 0
fi

if [[ -f "$live" ]]; then
  cp -p "$live" "$live.pre-deploy-$timestamp"
fi
mv "$candidate" "$live"
trap - EXIT

if "$build"; then
  docker compose --env-file "$env_file" -f "$live" build
fi
docker compose --env-file "$env_file" -f "$live" up -d --pull missing
docker compose --env-file "$env_file" -f "$live" ps