#!/usr/bin/env bash
set -euo pipefail

# Deterministic static analysis (Lint + local SonarQube Quality Gate)
# Usage: quality-check.sh [--lint-only | --sonar-only | --up]

MODE="all"
AUTO_UP=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lint-only)
      MODE="lint"
      shift
      ;;
    --sonar-only)
      MODE="sonar"
      shift
      ;;
    --up)
      AUTO_UP=true
      shift
      ;;
    -h|--help)
      echo "Usage: quality-check.sh [--lint-only | --sonar-only | --up]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

ROOT_DIR="$(pwd)"
if [[ -f "$ROOT_DIR/.sonarqube/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.sonarqube/.env"
  set +a
fi

SONAR_HOST_URL="${SONAR_HOST_URL:-http://localhost:9000}"
SONAR_AUTH_USER="${SONAR_TOKEN:-${SONAR_USER:-admin}}"
SONAR_AUTH_PASS="${SONAR_TOKEN:+}"
if [[ -z "${SONAR_TOKEN:-}" ]]; then
  SONAR_AUTH_PASS="${SONAR_PASSWORD:-admin}"
fi

run_lint() {
  echo "=== [1/2] Running Lint Checks ==="
  local ran_any=false

  # Optional custom lintCommand in .spec-kit.json
  if [[ -f "$ROOT_DIR/.spec-kit.json" ]] && command -v python3 >/dev/null 2>&1; then
    local custom_lint
    custom_lint="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("lintCommand",""))' "$ROOT_DIR/.spec-kit.json" 2>/dev/null || true)"
    if [[ -n "$custom_lint" ]]; then
      echo "Running configured lintCommand: $custom_lint"
      bash -c "$custom_lint"
      return $?
    fi
  fi

  # Node / Frontend lint
  for pkg in "$ROOT_DIR/package.json" "$ROOT_DIR/frontend/package.json"; do
    if [[ -f "$pkg" ]] && command -v npm >/dev/null 2>&1; then
      if grep -q '"lint"' "$pkg"; then
        local pkg_dir
        pkg_dir="$(dirname "$pkg")"
        echo "Running npm run lint in $pkg_dir..."
        (cd "$pkg_dir" && npm run lint)
        ran_any=true
      fi
    fi
  done

  # Python ruff / flake8
  if [[ -f "$ROOT_DIR/pyproject.toml" || -f "$ROOT_DIR/ruff.toml" ]] && command -v ruff >/dev/null 2>&1; then
    echo "Running ruff check..."
    ruff check "$ROOT_DIR"
    ran_any=true
  fi

  # Go golangci-lint
  if [[ -f "$ROOT_DIR/go.mod" ]] && command -v golangci-lint >/dev/null 2>&1; then
    echo "Running golangci-lint..."
    golangci-lint run
    ran_any=true
  fi

  # Maven checkstyle / spotless (only if configured in pom.xml)
  for pom in "$ROOT_DIR/pom.xml" "$ROOT_DIR/backend/pom.xml"; do
    if [[ -f "$pom" ]] && command -v mvn >/dev/null 2>&1; then
      local pom_dir
      pom_dir="$(dirname "$pom")"
      if grep -q "spotless-maven-plugin" "$pom"; then
        echo "Running mvn spotless:check in $pom_dir..."
        (cd "$pom_dir" && mvn -q spotless:check)
        ran_any=true
      elif grep -q "maven-checkstyle-plugin" "$pom"; then
        echo "Running mvn checkstyle:check in $pom_dir..."
        (cd "$pom_dir" && mvn -q checkstyle:check)
        ran_any=true
      fi
    fi
  done

  if [[ "$ran_any" == "false" ]]; then
    echo "INFO: No lint script/tool detected. Configure 'lintCommand' in .spec-kit.json or add a lint script."
  else
    echo "OK: Lint checks passed."
  fi
}

sonar_is_up() {
  curl -fsS "${SONAR_HOST_URL}/api/system/status" 2>/dev/null | grep -q '"status":"UP"'
}

ensure_sonar_up() {
  if sonar_is_up; then
    return 0
  fi

  if [[ "$AUTO_UP" == "true" && -f "$ROOT_DIR/.sonarqube/docker-compose.yml" ]]; then
    echo "Starting local SonarQube via Docker Compose..."
    docker compose -f "$ROOT_DIR/.sonarqube/docker-compose.yml" up -d
    echo "Waiting for SonarQube to become UP at $SONAR_HOST_URL..."
    for _ in $(seq 1 90); do
      if sonar_is_up; then
        echo "OK: SonarQube is UP."
        return 0
      fi
      sleep 2
    done
    echo "ERROR: Timed out waiting for SonarQube at $SONAR_HOST_URL." >&2
    return 1
  fi

  echo "ERROR: SonarQube is not running at $SONAR_HOST_URL." >&2
  echo "Start it with: docker compose -f .sonarqube/docker-compose.yml up -d (or pass --up)." >&2
  return 1
}

run_sonar() {
  echo "=== [2/2] Running Local SonarQube Analysis ==="
  ensure_sonar_up

  if [[ ! -f "$ROOT_DIR/sonar-project.properties" ]]; then
    echo "ERROR: Missing sonar-project.properties in $ROOT_DIR." >&2
    return 1
  fi

  local project_key
  project_key="$(sed -nE 's/^sonar\.projectKey=(.*)$/\1/p' "$ROOT_DIR/sonar-project.properties" | head -n 1 | tr -d '[:space:]')"
  if [[ -z "$project_key" ]]; then
    echo "ERROR: sonar.projectKey is not set in sonar-project.properties." >&2
    return 1
  fi

  local auth_args=()
  if [[ -n "${SONAR_TOKEN:-}" ]]; then
    local sonar_major
    sonar_major="$(curl -fsS "${SONAR_HOST_URL}/api/system/status" 2>/dev/null | sed -nE 's/.*"version":"([0-9]+)\..*/\1/p' | head -n 1 || true)"
    if [[ -n "$sonar_major" && "$sonar_major" -ge 10 ]] 2>/dev/null; then
      auth_args+=("-Dsonar.token=${SONAR_TOKEN}")
    else
      auth_args+=("-Dsonar.login=${SONAR_TOKEN}")
    fi
  else
    auth_args+=("-Dsonar.login=${SONAR_AUTH_USER}" "-Dsonar.password=${SONAR_AUTH_PASS}")
  fi

  if command -v sonar-scanner >/dev/null 2>&1; then
    sonar-scanner -Dsonar.host.url="$SONAR_HOST_URL" "${auth_args[@]}"
  elif command -v docker >/dev/null 2>&1; then
    docker run --rm --network host \
      -v "$ROOT_DIR:/usr/src" \
      sonarsource/sonar-scanner-cli \
      -Dsonar.host.url="$SONAR_HOST_URL" "${auth_args[@]}"
  else
    echo "ERROR: Neither sonar-scanner nor docker is available." >&2
    return 1
  fi

  # Wait for Compute Engine task (via report-task.txt if present, otherwise via /api/ce/component)
  local report_task="$ROOT_DIR/.scannerwork/report-task.txt"
  if [[ -f "$report_task" ]]; then
    local ce_task_id
    ce_task_id="$(sed -nE 's/^ceTaskId=(.*)$/\1/p' "$report_task" | head -n 1 | tr -d '[:space:]')"
    if [[ -n "$ce_task_id" ]]; then
      echo "Waiting for SonarQube analysis task $ce_task_id..."
      for _ in $(seq 1 30); do
        local task_json
        task_json="$(curl -fsS -u "${SONAR_AUTH_USER}:${SONAR_AUTH_PASS}" "${SONAR_HOST_URL}/api/ce/task?id=${ce_task_id}")"
        if echo "$task_json" | grep -q '"status":"SUCCESS"'; then
          break
        elif echo "$task_json" | grep -qE '"status":"(FAILED|CANCELED)"'; then
          echo "ERROR: SonarQube CE task failed: $task_json" >&2
          return 1
        fi
        sleep 2
      done
    fi
  else
    echo "Waiting for SonarQube Compute Engine task for $project_key..."
    for _ in $(seq 1 30); do
      local ce_json ce_state
      ce_json="$(curl -fsS -u "${SONAR_AUTH_USER}:${SONAR_AUTH_PASS}" "${SONAR_HOST_URL}/api/ce/component?component=${project_key}")"
      ce_state="$(python3 - "$ce_json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
queue = data.get("queue") or []
current = data.get("current") or {}
if queue:
    print("PENDING")
elif current.get("status") in ("FAILED", "CANCELED"):
    print("FAILED")
elif current.get("status") == "SUCCESS":
    print("SUCCESS")
else:
    print("PENDING")
PY
)"
      if [[ "$ce_state" == "SUCCESS" ]]; then
        break
      elif [[ "$ce_state" == "FAILED" ]]; then
        echo "ERROR: SonarQube CE task failed: $ce_json" >&2
        return 1
      fi
      sleep 2
    done
  fi

  # Deterministic query of Quality Gate & open issues
  local qg_json issues_json
  qg_json="$(curl -fsS -u "${SONAR_AUTH_USER}:${SONAR_AUTH_PASS}" "${SONAR_HOST_URL}/api/qualitygates/project_status?projectKey=${project_key}")"
  issues_json="$(curl -fsS -u "${SONAR_AUTH_USER}:${SONAR_AUTH_PASS}" "${SONAR_HOST_URL}/api/issues/search?componentKeys=${project_key}&resolved=false&ps=20")"

  python3 - "$qg_json" "$issues_json" <<'PY'
import json, sys

qg = json.loads(sys.argv[1]).get("projectStatus", {})
issues_data = json.loads(sys.argv[2])
status = qg.get("status", "UNKNOWN")
total = issues_data.get("total", 0)

print(f"SonarQube Quality Gate: {status} (Open issues: {total})")
for cond in qg.get("conditions", []):
    print(f"  - {cond.get('metricKey')}: {cond.get('status')} (actual={cond.get('actualValue')}, threshold={cond.get('errorThreshold')})")

for issue in issues_data.get("issues", [])[:15]:
    comp = issue.get("component", "").split(":")[-1]
    line = issue.get("line", "?")
    sev = issue.get("severity", "?")
    typ = issue.get("type", "?")
    msg = issue.get("message", "")
    print(f"  [{sev}/{typ}] {comp}:{line} - {msg}")

if status != "OK":
    sys.exit(1)
PY
}

if [[ "$MODE" == "lint" || "$MODE" == "all" ]]; then
  run_lint
fi

if [[ "$MODE" == "sonar" || "$MODE" == "all" ]]; then
  run_sonar
fi
