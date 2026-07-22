# Postman Collection Example

This example shows how API Drift Healer repairs an outdated request field inside a Postman Collection v2.1 file and validates the healed collection with Newman.

## Scenario

The Postman request named `Create User` sends:

```json
{
  "name": "Test User",
  "userEmail": "qa_user@example.com"
}
```

The OpenAPI contract for `POST /users` requires:

```json
{
  "name": "Test User",
  "email_address": "qa_user@example.com"
}
```

The safe repair is:

```text
userEmail -> email_address
```

The collection also contains a Postman test:

```javascript
pm.test("Status code is 201", function () {
    pm.response.to.have.status(201);
});
```

Because the outdated request receives HTTP `400`, the original collection fails Newman.

After the safe patch, the healed request receives HTTP `201` and passes Newman.

## Runtime Flow

```text
Original collection
-> Newman FAIL
-> Static SAFE_PATCH
-> Temporary healed collection
-> Newman PASS
-> Validated output written
```

The main safety rule is:

```text
No Newman PASS, no validated Postman output.
```

## Files

```text
examples/postman/
|-- create-user.postman_collection.json
|-- openapi.yaml
`-- README.md
```

The local demo API is defined in:

```text
mock_server.py
```

## Requirements

The runtime validation demo requires:

- Python
- project dependencies
- Node.js
- Newman

Check Newman:

```bash
newman --version
```

## Dry Run

From the repository root:

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --dry-run
```

Expected static decision:

```text
Decision: SAFE_PATCH
Candidate: userEmail -> email_address
Score: 0.772
Threshold: 0.700
Confidence: High
```

Dry-run displays the source diff but does not run Newman or write a collection.

## Generate a Structurally Healed Collection

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --output create-user.healed.postman_collection.json
```

This command performs static healing only.

The original collection is preserved.

## Validate with Newman

Start the local API in a separate terminal:

```bash
python mock_server.py
```

Then run:

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --output create-user.validated.postman_collection.json \
  --validate-newman
```

Expected result:

```text
Static analysis: SAFE_PATCH
Original Newman: FAIL (exit code 1)
Healed Newman: PASS
Decision: VALIDATED
```

The output file is written only after the healed collection passes Newman.

## Optional Environment File

A Postman environment can be passed to both Newman runs:

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --environment demo.postman_environment.json \
  --validate-newman
```

## Configure the Newman Timeout

The default timeout is 120 seconds.

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --newman-timeout 45 \
  --validate-newman
```

## Original Collection Guard

By default, validation stops when the original collection already passes Newman.

This prevents the tool from presenting an unnecessary patch as a proven repair.

The guard can be disabled explicitly:

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --allow-original-pass \
  --validate-newman
```

## Run the Complete Demo

On macOS, Linux, WSL, or Git Bash:

```bash
./scripts/demo_postman.sh
```

From Windows PowerShell with Git Bash installed:

```powershell
bash scripts/demo_postman.sh
```

The script:

1. Checks Newman and the local demo API.
2. Starts the Flask mock server when needed.
3. Proves that the original collection fails Newman.
4. Runs deterministic static drift analysis.
5. creates a temporary healed collection.
6. proves that the healed collection passes Newman.
7. writes and verifies a validated output.
8. preserves the original collection.
9. removes temporary files.

## Current Scope

Supported:

- Postman Collection v2.1
- nested folders
- exact request names
- raw JSON object bodies
- one top-level field rename
- exact OpenAPI path and method matching
- deterministic safety scoring
- Newman runtime validation
- original-failure guard
- healed-pass requirement
- optional Postman environment file
- configurable Newman timeout
- separate validated output
- original collection protection

Not yet supported:

- form-data
- URL-encoded bodies
- GraphQL
- nested repairs
- multiple repairs
- referenced or composed OpenAPI schemas
- automatic multi-request validation