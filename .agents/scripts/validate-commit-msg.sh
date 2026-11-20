#!/usr/bin/env bash
set -euo pipefail

# Validates a commit message against Angular Conventional Commits:
# - Header: <type>(<optional-scope>)<!>: <subject> (max 60 chars)
# - Allowed types: feat|fix|build|ci|docs|perf|refactor|style|test|chore|revert
# - Mandatory blank line followed by a non-empty body describing the changes
#
# Usage:
#   validate-commit-msg.sh <commit-msg-file>
#   validate-commit-msg.sh --message "<full commit message>"

MSG_CONTENT=""

if [[ $# -eq 2 && "$1" == "--message" ]]; then
  MSG_CONTENT="$2"
elif [[ $# -eq 1 && -f "$1" ]]; then
  MSG_CONTENT="$(cat "$1")"
elif [[ $# -eq 0 && ! -t 0 ]]; then
  MSG_CONTENT="$(cat)"
else
  echo "Usage: validate-commit-msg.sh <file> | --message \"<msg>\"" >&2
  exit 2
fi

python3 - "$MSG_CONTENT" <<'PY'
import re
import sys

raw = sys.argv[1]
lines = [ln.rstrip("\r") for ln in raw.splitlines() if not ln.lstrip().startswith("#")]

while lines and not lines[-1].strip():
    lines.pop()

if not lines:
    print("ERROR: Commit message is empty.", file=sys.stderr)
    sys.exit(1)

header = lines[0]

# Allow merge / revert auto-generated headers if needed? No, enforce standard unless Merge
if header.startswith("Merge "):
    print("OK: Merge commit header allowed.")
    sys.exit(0)

HEADER_RE = re.compile(
    r"^(feat|fix|build|ci|docs|perf|refactor|style|test|chore|revert)(\([a-z0-9._/-]+\))?(!)?: .+$"
)

errors = []
if not HEADER_RE.match(header):
    errors.append(
        "Header must follow Angular Conventional Commits: "
        "<type>(<scope>): <subject> "
        "(types: feat|fix|build|ci|docs|perf|refactor|style|test|chore|revert)."
    )

if len(header) > 60:
    errors.append(f"Header is {len(header)} chars (max 60): '{header}'")

if len(lines) < 3 or lines[1].strip() != "":
    errors.append("Commit message must have a blank line after the header followed by a body.")
else:
    body_lines = [ln for ln in lines[2:] if ln.strip()]
    if not body_lines:
        errors.append("Commit body cannot be empty; describe the changes.")

if errors:
    for err in errors:
        print(f"ERROR: {err}", file=sys.stderr)
    sys.exit(1)

print(f"OK: Commit message valid ({len(header)}/60 chars).")
PY
