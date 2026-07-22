# API Drift Healer 🛠️

**Current release: V1.1 — `.http` File Adapter**

API Drift Healer detects request-field drift between OpenAPI contracts and API tests.

It currently supports:

- YAML API test cases
- Postman Collection v2.1 files
- VS Code REST Client-style `.http` files
- deterministic field matching
- safe patch decisions
- human-readable diffs
- separate healed output files
- dry-run analysis

The main example is simple:

```text
OpenAPI requires:  email_address
Test still sends:  userEmail

Safe repair:
userEmail -> email_address
```

The matching decision is deterministic. No LLM decides whether a patch is safe.

---

## Postman Adapter

V1 can read a Postman collection, locate one request, compare its raw JSON body with OpenAPI, and generate a patched collection.

```text
Postman collection
        ↓
Normalized request
        ↓
OpenAPI path and method resolver
        ↓
Deterministic drift analyzer
        ↓
Safe field patch
        ↓
Diff
        ↓
Healed Postman collection
```

### Dry Run

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --dry-run
```

Expected result:

```text
Decision: SAFE_PATCH
Candidate: userEmail -> email_address
Score: 0.772
Threshold: 0.700
Confidence: High
```

The CLI also displays a field-level diff:

```diff
 {
   "name": "Test User",
-  "userEmail": "qa_user@example.com"
+  "email_address": "qa_user@example.com"
 }
```

Dry-run does not write any files.

### Generate a Healed Collection

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --output create-user.healed.postman_collection.json
```

The original collection is preserved.

The generated collection contains:

```json
{
  "name": "Test User",
  "email_address": "qa_user@example.com"
}
```

### One-Command Postman Demo

```bash
./scripts/demo_postman.sh
```

The demo:

1. reads the outdated Postman request
2. resolves `POST /users` from OpenAPI
3. detects `userEmail -> email_address`
4. shows the safe patch decision
5. displays the body diff
6. creates a temporary healed collection
7. validates the generated JSON
8. verifies that the original collection was preserved

No server is required for this structural Postman demo.

---


## `.http` File Adapter

V1.1 adds support for API requests stored in `.http` files, commonly used with VS Code REST Client and similar tools.

Example outdated request:

```http
### Create User
POST http://localhost:3000/users
Content-Type: application/json

{
  "name": "Test User",
  "userEmail": "qa_user@example.com"
}
```

The OpenAPI contract requires `email_address`.

The adapter converts the request into the same format-independent `NormalizedRequest` model used by the Postman adapter.

```text
.http file
    ↓
HTTP file adapter
    ↓
NormalizedRequest
    ↓
OpenAPI path and method resolver
    ↓
Deterministic drift analyzer
    ↓
Format-preserving field patch
    ↓
Healed .http file
```

### Dry Run

```bash
api-drift-healer http heal \
  --file examples/http/create-user.http \
  --openapi examples/http/openapi.yaml \
  --dry-run
```

Expected result:

```text
Decision: SAFE_PATCH
Candidate: userEmail -> email_address
Score: 0.772
Threshold: 0.700
Confidence: High
```

Dry-run displays the proposed diff without writing a file.

### Generate a Healed `.http` File

```bash
api-drift-healer http heal \
  --file examples/http/create-user.http \
  --openapi examples/http/openapi.yaml
```

The original file remains unchanged.

The generated file is:

```text
examples/http/create-user.healed.http
```

Only the matching top-level JSON key is renamed. The request line, headers, comments, indentation, values, and newline format are preserved.

### One-Command HTTP Demo

```bash
./scripts/demo_http.sh
```

The demo:

1. reads the outdated `.http` request
2. matches `POST /users` with OpenAPI
3. detects `userEmail -> email_address`
4. displays the safe patch decision and diff
5. generates a temporary healed `.http` file
6. validates the repaired request body
7. verifies that the original file and formatting were preserved

No API server is required for this structural demo.

---

## YAML Healing Flow

The existing YAML flow is still supported.

```text
400 FAIL
    ↓
SAFE FIELD PATCH
    ↓
201 PASS
    ↓
OPTIONAL APPLY OR PR
```

> **Golden Rule: No PASS, no apply. No PASS, no PR.**

Start the local mock API:

```bash
python mock_server.py
```

In another terminal, preview the YAML repair:

```bash
api-drift-healer heal \
  --test examples/basic_yaml/api_test_case.yaml \
  --openapi examples/basic_yaml/openapi.yaml \
  --dry-run
```

Generate and validate the healed YAML test:

```bash
api-drift-healer heal \
  --test examples/basic_yaml/api_test_case.yaml \
  --openapi examples/basic_yaml/openapi.yaml \
  --output examples/basic_yaml/api_test_case.healed.yaml
```

Run the full YAML demo:

```bash
./scripts/demo_basic_yaml.sh
```

The YAML flow runs the original request and the healed request against the local mock API.

---

## Installation

API Drift Healer requires Python 3.10 or newer.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Verify the CLI:

```bash
api-drift-healer --help
api-drift-healer heal --help
api-drift-healer postman heal --help
```

---


## HTTP File CLI Options

```text
--file       Single-request .http file. Required.
--openapi    OpenAPI contract file. Required.
--output     Path for the generated healed .http file.
--dry-run    Analyze and display the diff without writing a file.
--overwrite  Allow an existing output file to be replaced.
```

Example:

```bash
api-drift-healer http heal \
  --file examples/http/create-user.http \
  --openapi examples/http/openapi.yaml \
  --dry-run
```

## Postman CLI Options

```text
--collection  Postman Collection v2.1 JSON file. Required.
--request     Exact Postman request name. Required.
--openapi     OpenAPI YAML or JSON file. Required.
--output      Path for the healed collection.
--dry-run     Show the decision and diff without writing.
--overwrite   Replace an existing output file.
```

Exit codes:

```text
0  Safe patch generated, dry-run succeeded, or no drift found
1  Patch rejected or drift is too complex
2  Invalid input, unsupported format, or unsafe output path
```

---

## YAML CLI Options

```text
--test       YAML API test file. Required.
--openapi    OpenAPI contract file. Required.
--output     Path for the generated healed YAML test.
--dry-run    Analyze without writing files.
--apply      Apply a validated patch to the original test.
--create-pr  Open a Pull Request after validated apply.
```

Invalid combinations are rejected:

```text
--dry-run + --apply
--dry-run + --create-pr
--create-pr without --apply
```

---

## Safety Rules

API Drift Healer only accepts a field repair when:

- exactly one required OpenAPI field is missing
- exactly one unknown request field exists
- field-name similarity is strong enough
- semantic concepts are compatible
- value type matches the OpenAPI type
- detected value format matches the OpenAPI format
- no hard qualifier conflict is found
- the score reaches the `0.700` safety threshold

Examples:

```text
userEmail -> email_address   SAFE
displayName -> email_address REJECT
firstName -> last_name       REJECT
```

For Postman collections:

```text
No safe match, no output file.
```

For YAML tests:

```text
No PASS, no apply.
No PASS, no PR.
```

---

## Currently Supported


### `.http` Files

- REST Client-style `.http` request files
- one request per file
- full URLs and absolute paths
- request headers preserved
- raw JSON object bodies
- exact OpenAPI path and HTTP method matching
- one top-level field rename
- dry-run analysis
- unified source diff
- format-preserving patching
- LF and CRLF newline preservation
- separate healed `.http` output
- original-file protection
- overwrite protection

### Postman

- Postman Collection v2.1
- nested collection folders
- exact request-name selection
- raw JSON object bodies
- URL strings
- Postman URL objects
- base URL variables such as `{{baseUrl}}/users`
- exact OpenAPI path and HTTP method matching
- one top-level field rename
- dry-run analysis
- unified body diff
- separate healed collection output
- overwrite protection

### YAML

- local YAML API test cases
- request execution against a local API
- safe deterministic field matching
- healed test generation
- local validation
- explainability reports
- optional validated apply
- optional GitHub Pull Request flow

---

## Current Limitations


The V1.1 `.http` adapter currently supports one request per file.

It does not currently support:

- multiple requests separated by `###`
- request variables such as `{{baseUrl}}`
- form-data bodies
- URL-encoded bodies
- GraphQL bodies
- XML bodies
- JavaScript request scripts
- nested JSON field repairs
- multiple field repairs in one request
- JSON arrays as the top-level request body

The V1 Postman adapter does not currently support:

- form-data bodies
- URL-encoded bodies
- GraphQL bodies
- XML bodies
- JavaScript-generated request bodies
- nested JSON field repairs
- multiple field repairs in one request
- OpenAPI `$ref` request schemas
- `allOf`, `oneOf`, or `anyOf` schemas
- fuzzy OpenAPI path-template matching
- Newman runtime validation
- automatic Postman Pull Request creation

Newman runtime validation is planned for V1.2.

The generated collection is currently validated as JSON and checked through the normalized request model. It is not yet executed against a live API by Newman.

---

## Architecture

```text
Input Adapter
    ↓
NormalizedRequest
    ↓
OpenAPI Resolver
    ↓
ResolvedRequestSchema
    ↓
Drift Analyzer
    ↓
SAFE_PATCH / REJECTED / NO_DRIFT / COMPLEX_DRIFT
    ↓
Format-specific Patcher
```

The core analyzer does not depend on Postman, `.http` files, or YAML.

This makes it possible to add other adapters later without rebuilding the safety engine.

---

## Project Structure

```text
api-drift-healer-demo/
├── api_drift_healer/
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── postman.py
│   ├── __init__.py
│   ├── cli.py
│   ├── drift_analyzer.py
│   ├── models.py
│   ├── openapi_resolver.py
│   └── postman_healer.py
├── examples/
│   ├── basic_yaml/
│   │   ├── README.md
│   │   ├── api_test_case.yaml
│   │   └── openapi.yaml
│   └── postman/
│       ├── README.md
│       ├── create-user.postman_collection.json
│       └── openapi.yaml
├── scripts/
│   ├── demo_basic_yaml.sh
│   └── demo_postman.sh
├── auto_healer.py
├── field_matcher.py
├── mock_server.py
├── test_runner.py
├── pyproject.toml
└── README.md
```

---

## Automated Tests

Run all tests:

```bash
python -m unittest discover
```

Current V1 test suite:

```text
153 automated tests
```

Coverage includes:

- field normalization and semantic matching
- OpenAPI type and format checks
- hard conflict rejection
- normalized request models
- Postman collection parsing
- nested Postman folders
- OpenAPI endpoint resolution
- format-independent drift analysis
- safe Postman body patching
- healed collection writing
- overwrite protection
- Postman service flow
- Postman CLI behavior
- YAML CLI backward compatibility
- one-command demo scripts
- original-file preservation
- `.http` request parsing
- LF and CRLF newline handling
- multiple-request rejection
- format-preserving HTTP body patching
- HTTP healing service flow
- HTTP CLI behavior
- one-command HTTP demo validation

---

## Current Status

```text
V0.4 ✅ Deterministic smart field matching
V0.5 ✅ Installable Typer CLI
V0.6 ✅ Runnable YAML example and one-command demo

V1.0 ✅ Format-independent request model
V1.0 ✅ Postman Collection v2.1 parser
V1.0 ✅ Nested request discovery
V1.0 ✅ OpenAPI path and method resolver
V1.0 ✅ Format-independent drift analyzer
V1.0 ✅ Safe Postman body patcher
V1.0 ✅ Healed collection writer
V1.0 ✅ Postman dry-run and diff
V1.0 ✅ Postman CLI
V1.0 ✅ One-command Postman demo

V1.1 ✅ Single-request `.http` parser
V1.1 ✅ Method, URL, path, and JSON body extraction
V1.1 ✅ LF and CRLF newline preservation
V1.1 ✅ Multiple-request safety rejection
V1.1 ✅ Format-preserving top-level field patcher
V1.1 ✅ HTTP healing service
V1.1 ✅ `.http` dry-run and source diff
V1.1 ✅ `.http` CLI
V1.1 ✅ Separate healed `.http` output
V1.1 ✅ One-command HTTP demo
V1.1 ✅ 153 automated tests
```

---

## Roadmap

### V1.2 — Newman Runtime Validation

- optionally run the original Postman collection with Newman
- run the healed collection after a safe patch
- require a passing Newman result before marking the output as validated
- support Postman environment files
- preserve the rule: no Newman PASS, no validated apply

### V1.3 — Pytest / Requests Adapter

- locate simple Python request payloads
- associate payloads with URLs and methods
- preserve surrounding test logic
- reject risky rewrites

### V1.4 — Multiple Requests and Tests

- select one request from multi-request `.http` files
- support multiple Postman requests in one healing run
- produce a combined analysis report
- reject ambiguous cross-request patches

### V2 — CI Integration

- run inside GitHub Actions
- react to failed API tests
- generate reports or Pull Requests
- keep human review before merge

### V3 — Local LLM Explanation Layer

```text
Deterministic code decides.
Tests validate.
AI explains.
Humans review.
```

An LLM will not be trusted as the patch engine.

---

## What This Is Not

API Drift Healer is not:

- a complete API testing platform
- a replacement for QA engineers
- a blind AI auto-fix bot
- a universal test-repair system
- a tool that automatically merges changes
- a guarantee that every drift can be repaired

It is a focused local-first tool for safely handling simple API contract drift.
