#!/usr/bin/env bash
set -euo pipefail

# Updates managed harness rules & skills from agent-spec-kit without overwriting AGENTS.md or .specs/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$TARGET_DIR/.spec-kit.json"

REPO_URL="$(sed -nE 's/.*"repo"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p' "$CONFIG_FILE" | head -n 1)"
REF="$(sed -nE 's/.*"ref"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p' "$CONFIG_FILE" | head -n 1)"

REPO_URL="${REPO_URL:-https://github.com/tiaggofg/agent-spec-kit.git}"
REF="${REF:-main}"

LOCAL_KIT=""
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      LOCAL_KIT="$2"
      shift 2
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -n "$LOCAL_KIT" ]]; then
  exec bash "$LOCAL_KIT/scripts/install.sh" --target "$TARGET_DIR" --local "$LOCAL_KIT" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
git clone --depth 1 --branch "$REF" "$REPO_URL" "$TMP_DIR/kit" >/dev/null 2>&1
exec bash "$TMP_DIR/kit/scripts/install.sh" --target "$TARGET_DIR" --local "$TMP_DIR/kit" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
