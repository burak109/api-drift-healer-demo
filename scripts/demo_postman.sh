#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
  pwd
)"

cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python}"

COLLECTION_FILE="examples/postman/create-user.postman_collection.json"
OPENAPI_FILE="examples/postman/openapi.yaml"
REQUEST_NAME="Create User"

TEMP_DIRECTORY="$(mktemp -d)"
HEALED_FILE="$TEMP_DIRECTORY/create-user.healed.postman_collection.json"

cleanup() {
  rm -rf "$TEMP_DIRECTORY"
}

trap cleanup EXIT

echo "============================================================"
echo " API DRIFT HEALER V1 - POSTMAN ADAPTER DEMO"
echo "============================================================"
echo

echo "[1/5] Inspecting the outdated Postman request..."
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
echo "[2/5] Running safe drift analysis..."
echo

"$PYTHON_BIN" -m api_drift_healer.cli postman heal \
  --collection "$COLLECTION_FILE" \
  --request "$REQUEST_NAME" \
  --openapi "$OPENAPI_FILE" \
  --dry-run

echo
echo "[3/5] Generating the healed Postman collection..."
echo

"$PYTHON_BIN" -m api_drift_healer.cli postman heal \
  --collection "$COLLECTION_FILE" \
  --request "$REQUEST_NAME" \
  --openapi "$OPENAPI_FILE" \
  --output "$HEALED_FILE"

echo
echo "[4/5] Validating the generated collection..."
echo

"$PYTHON_BIN" -m json.tool "$HEALED_FILE" > /dev/null

echo "PASS: healed collection contains valid JSON."

"$PYTHON_BIN" - "$COLLECTION_FILE" "$HEALED_FILE" <<'PY'
import sys

from api_drift_healer.adapters.postman import (
    normalize_postman_request_file,
)

original_path = sys.argv[1]
healed_path = sys.argv[2]

original = normalize_postman_request_file(
    collection_path=original_path,
    request_name="Create User",
)

healed = normalize_postman_request_file(
    collection_path=healed_path,
    request_name="Create User",
)

assert "userEmail" in original.body
assert "email_address" not in original.body

assert "userEmail" not in healed.body
assert (
    healed.body["email_address"]
    == original.body["userEmail"]
)

print(f"Original body: {original.body}")
print(f"Healed body:  {healed.body}")
print()
print("PASS: original collection was preserved.")
print("PASS: userEmail was removed from the healed request.")
print("PASS: email_address contains the original value.")
PY

echo
echo "[5/5] Demo summary"
echo
echo "Original field : userEmail"
echo "Required field : email_address"
echo "Decision       : SAFE_PATCH"
echo "Result         : Healed Postman collection generated"
echo "Validation     : JSON and request body verified"
echo
echo "============================================================"
echo " POSTMAN DEMO COMPLETED SUCCESSFULLY"
echo "============================================================"
