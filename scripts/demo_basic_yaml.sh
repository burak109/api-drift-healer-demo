#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TEST_FILE="examples/basic_yaml/api_test_case.yaml"
OPENAPI_FILE="examples/basic_yaml/openapi.yaml"
HEALED_FILE="examples/basic_yaml/api_test_case.healed.yaml"
REPORT_FILE="examples/basic_yaml/heal_report.md"

SERVER_LOG="/tmp/api-drift-healer-server.log"
DRY_RUN_LOG="/tmp/api-drift-healer-dry-run.log"
HEAL_LOG="/tmp/api-drift-healer-heal.log"

SERVER_PID=""

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi

  rm -f "$HEALED_FILE"
  rm -f "$REPORT_FILE"
}

trap cleanup EXIT INT TERM

if ! command -v api-drift-healer >/dev/null 2>&1; then
  echo "ERROR: api-drift-healer is not installed."
  echo "Run: python -m pip install -e ."
  exit 1
fi

if lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: Port 3000 is already in use."
  lsof -nP -iTCP:3000 -sTCP:LISTEN
  exit 1
fi

rm -f "$HEALED_FILE"
rm -f "$REPORT_FILE"

echo
echo "========================================"
echo " API DRIFT HEALER - BASIC YAML DEMO"
echo "========================================"
echo
echo "OpenAPI requires : email_address"
echo "Test currently   : userEmail"
echo

echo "[1/4] Starting mock API..."

python mock_server.py > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

for attempt in $(seq 1 20); do
  if curl -s -o /dev/null http://127.0.0.1:3000/users; then
    break
  fi

  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "ERROR: Mock API stopped unexpectedly."
    cat "$SERVER_LOG"
    exit 1
  fi

  sleep 0.25
done

if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "ERROR: Mock API could not start."
  cat "$SERVER_LOG"
  exit 1
fi

echo "Mock API is running."

echo
echo "[2/4] Detecting contract drift..."

api-drift-healer heal \
  --test "$TEST_FILE" \
  --openapi "$OPENAPI_FILE" \
  --dry-run \
  > "$DRY_RUN_LOG"

grep -E \
  '^\[FAIL\]|Safe Drift Match Detected|\[DRY RUN\] Candidate:|\[DRY RUN\] Score:|\[DRY RUN\] Decision:' \
  "$DRY_RUN_LOG" || true

echo
echo "[3/4] Generating and validating repair..."

api-drift-healer heal \
  --test "$TEST_FILE" \
  --openapi "$OPENAPI_FILE" \
  --output "$HEALED_FILE" \
  > "$HEAL_LOG"

grep -E \
  '^\[FAIL\]|^\[PASS\]|Healed test file generated|Healed test validated successfully' \
  "$HEAL_LOG" || true

echo
echo "[4/4] Validated change:"
echo

diff -u "$TEST_FILE" "$HEALED_FILE" || true

echo
echo "========================================"
echo " RESULT"
echo "========================================"
echo
echo "Original test : 400 FAIL"
echo "Safe patch    : userEmail -> email_address"
echo "Healed test   : 201 PASS"
echo
echo "No PASS, no accepted patch."
echo
echo "Demo completed successfully."
