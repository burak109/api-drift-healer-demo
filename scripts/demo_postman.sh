#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
  pwd
)"

cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python}"
NEWMAN_BIN="${NEWMAN_BIN:-newman}"

COLLECTION_FILE="examples/postman/create-user.postman_collection.json"
OPENAPI_FILE="examples/postman/openapi.yaml"
MOCK_SERVER_FILE="mock_server.py"
REQUEST_NAME="Create User"

TEMP_DIRECTORY="$(mktemp -d)"

VALIDATED_FILE="$TEMP_DIRECTORY/create-user.validated.postman_collection.json"
MOCK_SERVER_LOG="$TEMP_DIRECTORY/mock-server.log"
ORIGINAL_NEWMAN_LOG="$TEMP_DIRECTORY/original-newman.log"
VALIDATION_LOG="$TEMP_DIRECTORY/validation.log"
FINAL_NEWMAN_LOG="$TEMP_DIRECTORY/final-newman.log"

SERVER_PID=""
STARTED_SERVER=0


cleanup() {
  if [[ "$STARTED_SERVER" -eq 1 && -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi

  rm -rf "$TEMP_DIRECTORY"
}


trap cleanup EXIT INT TERM


check_demo_api() {
  "$PYTHON_BIN" - <<'PY'
import sys

import requests


try:
    response = requests.post(
        "http://127.0.0.1:3000/users",
        json={
            "name": "Runtime Check",
        },
        timeout=0.5,
    )
except requests.RequestException:
    sys.exit(1)

try:
    payload = response.json()
except ValueError:
    sys.exit(1)

expected_error = "missing required field: email_address"

if (
    response.status_code == 400
    and payload.get("error") == expected_error
):
    sys.exit(0)

sys.exit(1)
PY
}


echo "============================================================"
echo " API DRIFT HEALER V1.2 - NEWMAN VALIDATION DEMO"
echo "============================================================"
echo


echo "[1/6] Checking runtime dependencies and demo API..."
echo

if ! command -v "$NEWMAN_BIN" >/dev/null 2>&1; then
  echo "ERROR: Newman was not found on PATH."
  echo "Install Newman before running this demo."
  exit 1
fi

echo "Python: $PYTHON_BIN"
echo "Newman: $NEWMAN_BIN"

if check_demo_api; then
  echo "PASS: compatible demo API is already running on port 3000."
else
  echo "Starting the local Flask mock server..."

  "$PYTHON_BIN" "$MOCK_SERVER_FILE" \
    >"$MOCK_SERVER_LOG" 2>&1 &

  SERVER_PID=$!
  STARTED_SERVER=1

  for _ in {1..50}; do
    if check_demo_api; then
      break
    fi

    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      echo
      echo "ERROR: mock server stopped unexpectedly."
      cat "$MOCK_SERVER_LOG"
      exit 1
    fi

    sleep 0.2
  done

  if ! check_demo_api; then
    echo
    echo "ERROR: mock server did not become ready."
    cat "$MOCK_SERVER_LOG"
    exit 1
  fi

  echo "PASS: local Flask mock server started."
fi


echo
echo "[2/6] Inspecting the outdated Postman request..."
echo

"$PYTHON_BIN" - "$COLLECTION_FILE" "$OPENAPI_FILE" <<'PY'
import sys

from api_drift_healer.adapters.postman import (
    normalize_postman_request_file,
)
from api_drift_healer.openapi_resolver import (
    resolve_request_schema_file,
)


collection_path = sys.argv[1]
openapi_path = sys.argv[2]

request = normalize_postman_request_file(
    collection_path=collection_path,
    request_name="Create User",
)

schema = resolve_request_schema_file(
    openapi_path=openapi_path,
    method=request.method,
    path=request.path,
)

print(f"Request:          {request.name}")
print(f"Endpoint:         {request.method} {request.path}")
print(f"Current body:     {request.body}")
print(f"Required fields:  {schema.required_fields}")
PY


echo
echo "[3/6] Proving the original collection fails Newman..."
echo

set +e

"$NEWMAN_BIN" run "$COLLECTION_FILE" \
  2>&1 | tee "$ORIGINAL_NEWMAN_LOG"

ORIGINAL_EXIT_CODE=${PIPESTATUS[0]}

set -e

if [[ "$ORIGINAL_EXIT_CODE" -eq 0 ]]; then
  echo
  echo "ERROR: the original collection unexpectedly passed Newman."
  exit 1
fi

if ! grep -q \
  "expected response to have status code 201 but got 400" \
  "$ORIGINAL_NEWMAN_LOG"; then
  echo
  echo "ERROR: Newman failed, but not for the expected API drift."
  exit 1
fi

echo
echo "PASS: original collection failed Newman as expected."
echo "PASS: outdated userEmail field produced HTTP 400."


echo
echo "[4/6] Running the validated healing flow..."
echo

"$PYTHON_BIN" -m api_drift_healer.cli postman heal \
  --collection "$COLLECTION_FILE" \
  --request "$REQUEST_NAME" \
  --openapi "$OPENAPI_FILE" \
  --output "$VALIDATED_FILE" \
  --validate-newman \
  --overwrite \
  2>&1 | tee "$VALIDATION_LOG"

grep -q \
  "Static analysis: SAFE_PATCH" \
  "$VALIDATION_LOG"

grep -q \
  "Original Newman: FAIL" \
  "$VALIDATION_LOG"

grep -q \
  "Healed Newman: PASS" \
  "$VALIDATION_LOG"

grep -q \
  "Decision: VALIDATED" \
  "$VALIDATION_LOG"

echo
echo "PASS: runtime validation returned VALIDATED."


echo
echo "[5/6] Verifying the validated collection..."
echo

"$PYTHON_BIN" -m json.tool \
  "$VALIDATED_FILE" \
  > /dev/null

echo "PASS: validated collection contains valid JSON."

"$PYTHON_BIN" - "$COLLECTION_FILE" "$VALIDATED_FILE" <<'PY'
import sys

from api_drift_healer.adapters.postman import (
    normalize_postman_request_file,
)


original_path = sys.argv[1]
validated_path = sys.argv[2]

original = normalize_postman_request_file(
    collection_path=original_path,
    request_name="Create User",
)

validated = normalize_postman_request_file(
    collection_path=validated_path,
    request_name="Create User",
)

assert "userEmail" in original.body
assert "email_address" not in original.body

assert "userEmail" not in validated.body
assert "email_address" in validated.body

assert (
    validated.body["email_address"]
    == original.body["userEmail"]
)

print(f"Original body:   {original.body}")
print(f"Validated body:  {validated.body}")
print()
print("PASS: original collection was preserved.")
print("PASS: userEmail was removed from the validated request.")
print("PASS: email_address contains the original value.")
PY


echo
echo "[6/6] Running the validated collection with Newman..."
echo

"$NEWMAN_BIN" run "$VALIDATED_FILE" \
  2>&1 | tee "$FINAL_NEWMAN_LOG"

echo
echo "PASS: validated collection passed Newman."


echo
echo "============================================================"
echo " Demo summary"
echo "============================================================"
echo
echo "Original field : userEmail"
echo "Required field : email_address"
echo "Decision: SAFE_PATCH"
echo "Original Newman: FAIL"
echo "Healed Newman  : PASS"
echo "Final decision : VALIDATED"
echo "Output policy  : No Newman PASS, no validated output"
echo
echo "============================================================"
echo " POSTMAN DEMO COMPLETED SUCCESSFULLY"
echo "============================================================"