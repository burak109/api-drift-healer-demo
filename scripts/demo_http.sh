#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
  pwd
)"

cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python}"

HTTP_FILE="examples/http/create-user.http"
OPENAPI_FILE="examples/http/openapi.yaml"

TEMP_DIRECTORY="$(mktemp -d)"
HEALED_FILE="$TEMP_DIRECTORY/create-user.healed.http"

cleanup() {
  rm -rf "$TEMP_DIRECTORY"
}

trap cleanup EXIT

echo "============================================================"
echo " API DRIFT HEALER V1.1 - HTTP FILE ADAPTER DEMO"
echo "============================================================"
echo

echo "[1/4] Running dry-run analysis..."
echo

"$PYTHON_BIN" -m api_drift_healer.cli http heal \
  --file "$HTTP_FILE" \
  --openapi "$OPENAPI_FILE" \
  --dry-run

echo
echo "[2/4] Generating healed HTTP file..."
echo

"$PYTHON_BIN" -m api_drift_healer.cli http heal \
  --file "$HTTP_FILE" \
  --openapi "$OPENAPI_FILE" \
  --output "$HEALED_FILE"

echo
echo "[3/4] Validating output..."
echo

"$PYTHON_BIN" - "$HTTP_FILE" "$HEALED_FILE" <<'PY'
import sys
from pathlib import Path

from api_drift_healer.adapters.http_file import parse_http_file

original_path = Path(sys.argv[1])
healed_path = Path(sys.argv[2])

original = parse_http_file(original_path)
healed = parse_http_file(healed_path)

assert "userEmail" in original.request.body
assert "email_address" not in original.request.body

assert "userEmail" not in healed.request.body
assert (
    healed.request.body["email_address"]
    == original.request.body["userEmail"]
)

restored = healed.source_text.replace(
    '"email_address"',
    '"userEmail"',
    1,
)

assert restored == original.source_text

print(f"Original body: {original.request.body}")
print(f"Healed body:  {healed.request.body}")
print()
print("PASS: original HTTP file was preserved.")
print("PASS: healed HTTP body is valid.")
print("PASS: request formatting was preserved.")
PY

echo
echo "[4/4] Demo summary"
echo
echo "Original field : userEmail"
echo "Required field : email_address"
echo "Decision       : SAFE_PATCH"
echo "Result         : Healed HTTP file generated"
echo
echo "============================================================"
echo " HTTP FILE DEMO COMPLETED SUCCESSFULLY"
echo "============================================================"