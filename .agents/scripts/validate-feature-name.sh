#!/usr/bin/env bash
set -euo pipefail

# Validates feature folder names under .specs/features/ against ^[0-9]+-[a-zA-Z][a-zA-Z0-9-]*$
# Examples: 1-login, 01-user-auth, 001-secret-santa

PATTERN='^[0-9]+-[a-zA-Z][a-zA-Z0-9-]*$'

validate_name() {
  local name="$1"
  if [[ ! "$name" =~ $PATTERN ]]; then
    echo "ERROR: Invalid feature name '$name'. Expected pattern: [0-9]+-[a-zA-Z][a-zA-Z0-9-]* (e.g., 01-user-auth, 001-checkout)." >&2
    return 1
  fi
  echo "OK: Feature name '$name' is valid."
}

if [[ $# -ge 1 ]]; then
  for arg in "$@"; do
    base="$(basename "$arg")"
    validate_name "$base"
  done
  exit 0
fi

if [[ ! -d ".specs/features" ]]; then
  echo "OK: No .specs/features directory yet."
  exit 0
fi

failed=0
for dir in .specs/features/*; do
  [[ -d "$dir" ]] || continue
  base="$(basename "$dir")"
  if ! validate_name "$base"; then
    failed=1
  fi
done

exit "$failed"
