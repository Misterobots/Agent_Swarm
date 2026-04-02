#!/bin/bash
set -e

echo "--- free-code bootstrap: start ---"

if [ "${SWARM_API_KEY:-}" != "sk-coder-identity" ]; then
  echo "free-code bootstrap skipped: non-coding workspace"
  exit 0
fi

if [ "${FREE_CODE_ENABLE:-true}" != "true" ]; then
  echo "free-code bootstrap disabled via FREE_CODE_ENABLE"
  exit 0
fi

export HOME=/config
WORKSPACE_ROOT="/config/workspace"
FREE_CODE_DIR="${WORKSPACE_ROOT}/.hive/free-code"
MCP_CONFIG_PATH="${MCP_CONFIG_PATH:-/config/.config/free-code/mcp.json}"
MCP_DIR="$(dirname "${MCP_CONFIG_PATH}")"
MCP_FILE="${MCP_CONFIG_PATH}"
MCP_ENDPOINT="${MCP_ENDPOINT:-http://host.docker.internal:8008/api/v1/mcp/rpc}"
MCP_HEALTH_ENDPOINT="${MCP_HEALTH_ENDPOINT:-http://host.docker.internal:8008/api/v1/mcp/health}"
HIVE_BIN_DIR="${WORKSPACE_ROOT}/.hive/bin"
HIVE_CLI="${HIVE_BIN_DIR}/hive-mcp"

mkdir -p "${WORKSPACE_ROOT}/.hive"
mkdir -p "${MCP_DIR}"
mkdir -p "${HIVE_BIN_DIR}"

if ! command -v git >/dev/null 2>&1; then
  echo "git not available; skipping free-code clone"
  exit 0
fi

if [ ! -d "${FREE_CODE_DIR}/.git" ]; then
  echo "Cloning free-code repository..."
  git clone --depth=1 https://github.com/paoloanzn/free-code.git "${FREE_CODE_DIR}" || true
else
  echo "Updating free-code repository..."
  git -C "${FREE_CODE_DIR}" pull --ff-only || true
fi

if ! command -v bun >/dev/null 2>&1; then
  echo "bun not found; attempting user-space install"
  curl -fsSL https://bun.sh/install | bash || true
  export PATH="${HOME}/.bun/bin:${PATH}"
fi

if command -v bun >/dev/null 2>&1 && [ -f "${FREE_CODE_DIR}/package.json" ]; then
  echo "Installing free-code dependencies"
  cd "${FREE_CODE_DIR}"
  bun install || true
  echo "Building free-code full feature profile"
  bun run build:dev:full || true
fi

cat > "${MCP_FILE}" <<JSON
{
  "mcpServers": {
    "home-ai-lab": {
      "transport": "http",
      "url": "${MCP_ENDPOINT}",
      "headers": {
        "x-hive-client": "free-code"
      }
    }
  }
}
JSON

cat > "${HIVE_CLI}" <<'SH'
#!/bin/sh
set -eu

MCP_ENDPOINT="${MCP_ENDPOINT:-http://host.docker.internal:8008/api/v1/mcp/rpc}"
HIVE_BEARER_TOKEN="${HIVE_BEARER_TOKEN:-${SWARM_BEARER_TOKEN:-}}"

if [ "$#" -lt 1 ]; then
  echo "Usage: hive-mcp <run|read|write|list> [args...]"
  exit 1
fi

json_escape() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
    return
  fi
  escaped=$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')
  printf '"%s"' "$escaped"
}

cmd="$1"
shift || true

method_name=""
arguments='{}'

case "$cmd" in
  run)
    if [ "$#" -lt 1 ]; then
      echo "Usage: hive-mcp run <command>"
      exit 1
    fi
    method_name="hive.terminal.run"
    command_text="$*"
    arguments=$(printf '{"command": %s}' "$(json_escape "$command_text")")
    ;;
  read)
    if [ "$#" -ne 1 ]; then
      echo "Usage: hive-mcp read <path>"
      exit 1
    fi
    method_name="hive.fs.read"
    arguments=$(printf '{"path": %s}' "$(json_escape "$1")")
    ;;
  write)
    if [ "$#" -lt 2 ]; then
      echo "Usage: hive-mcp write <path> <content>"
      exit 1
    fi
    method_name="hive.fs.write"
    file_path="$1"
    shift
    file_content="$*"
    arguments=$(printf '{"path": %s, "content": %s}' \
      "$(json_escape "$file_path")" \
      "$(json_escape "$file_content")")
    ;;
  list)
    method_name="hive.fs.list"
    list_path="${1:-.}"
    arguments=$(printf '{"path": %s}' "$(json_escape "$list_path")")
    ;;
  *)
    echo "Unknown command: $cmd"
    echo "Supported: run, read, write, list"
    exit 1
    ;;
esac

payload=$(printf '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"%s","arguments":%s}}' "$method_name" "$arguments")

if [ -n "$HIVE_BEARER_TOKEN" ]; then
  http_code=$(curl -sS -o /tmp/.hive_resp -w "%{http_code}" -H "Content-Type: application/json" -H "x-hive-client: free-code" -H "Authorization: Bearer $HIVE_BEARER_TOKEN" -d "$payload" "$MCP_ENDPOINT" 2>/tmp/.hive_err)
else
  http_code=$(curl -sS -o /tmp/.hive_resp -w "%{http_code}" -H "Content-Type: application/json" -H "x-hive-client: free-code" -d "$payload" "$MCP_ENDPOINT" 2>/tmp/.hive_err)
fi

response=$(cat /tmp/.hive_resp 2>/dev/null)

# Network / HTTP error handling
if [ "$http_code" = "000" ]; then
  echo "error: cannot reach MCP bridge at $MCP_ENDPOINT" >&2
  echo "hint: check that agent_runtime is running and network is reachable" >&2
  cat /tmp/.hive_err >&2 2>/dev/null
  exit 1
elif [ "$http_code" -ge 500 ] 2>/dev/null; then
  echo "error: MCP bridge returned server error (HTTP $http_code)" >&2
  exit 1
elif [ "$http_code" -ge 400 ] 2>/dev/null; then
  echo "error: MCP bridge rejected request (HTTP $http_code)" >&2
  printf '%s\n' "$response" >&2
  exit 1
fi

# Parse response — prefer python3 but fall back to grep/sed
parse_response() {
  _resp="$1"
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$_resp" | python3 -c "
import json, sys
try:
    r = json.loads(sys.stdin.read())
    result = r.get('result', {})
    if result.get('isError'):
        msg = result.get('content', [{}])[0].get('text', 'unknown error')
        if 'Missing bearer token' in msg:
            print('error: authentication required', file=sys.stderr)
            print('hint: set HIVE_BEARER_TOKEN or run: export HIVE_BEARER_TOKEN=\$(hive-mcp-auth)', file=sys.stderr)
        elif 'Invalid token' in msg:
            print('error: token is invalid or expired', file=sys.stderr)
            print('hint: obtain a fresh token and re-export HIVE_BEARER_TOKEN', file=sys.stderr)
        elif 'Insufficient security level' in msg:
            print('error: your token does not have the required security level for this tool', file=sys.stderr)
            print('hint: this tool requires admin (L3_ADMIN) access', file=sys.stderr)
        elif 'capability' in msg.lower():
            print(f'error: missing capability — {msg}', file=sys.stderr)
        else:
            print(f'error: {msg}', file=sys.stderr)
        sys.exit(1)
    for c in result.get('content', []):
        print(c.get('text', ''))
except json.JSONDecodeError:
    print(_resp, file=sys.stderr)
"
    return $?
  fi

  # Shell-only fallback: detect isError and extract text message
  case "$_resp" in
    *'"isError":true'*|*'"isError": true'*)
      # Extract the text field from the first content object
      _msg=$(printf '%s' "$_resp" | sed 's/.*"text":"\([^"]*\)".*/\1/' 2>/dev/null)
      case "$_msg" in
        *"Missing bearer token"*)
          echo "error: authentication required" >&2
          echo "hint: set HIVE_BEARER_TOKEN or run: export HIVE_BEARER_TOKEN=\$(hive-mcp-auth)" >&2 ;;
        *"Invalid token"*)
          echo "error: token is invalid or expired" >&2
          echo "hint: obtain a fresh token and re-export HIVE_BEARER_TOKEN" >&2 ;;
        *"Insufficient security level"*)
          echo "error: insufficient security level for this tool" >&2
          echo "hint: this tool requires admin (L3_ADMIN) access" >&2 ;;
        *)
          echo "error: ${_msg:-unknown error}" >&2 ;;
      esac
      return 1
      ;;
    *)
      # Success — extract text content
      _text=$(printf '%s' "$_resp" | sed 's/.*"text":"\(.*\)".*/\1/' 2>/dev/null | sed 's/\\n/\n/g')
      if [ -n "$_text" ]; then
        printf '%s\n' "$_text"
      else
        printf '%s\n' "$_resp"
      fi
      return 0
      ;;
  esac
}

parse_response "$response"
SH

chmod +x "${HIVE_CLI}"

if [ -f /config/.profile ] && ! grep -q "\.hive/bin" /config/.profile; then
  echo 'export PATH="/config/workspace/.hive/bin:$PATH"' >> /config/.profile
fi

if command -v curl >/dev/null 2>&1; then
  if ! curl -fsS --max-time 5 "${MCP_HEALTH_ENDPOINT}" >/dev/null 2>&1; then
    echo "warning: MCP health check failed (${MCP_HEALTH_ENDPOINT}); free-code CLI bridge may be unavailable until runtime is reachable"
  fi
fi

echo "free-code MCP config written to: ${MCP_FILE}"
echo "CLI bridge installed: ${HIVE_CLI}"

echo "--- free-code bootstrap: done ---"
