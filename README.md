# API Drift Healer

**Current release: V1.4 - Multiple Requests and Tests**

API Drift Healer detects request-field drift between OpenAPI contracts and API tests.

It currently supports:

- YAML API test cases
- Postman Collection v2.1 files
- VS Code REST Client-style `.http` files
- pytest-style Python API tests that use `requests`
- deterministic field matching
- safe patch decisions
- human-readable diffs
- separate healed output files for writable adapters
- suggestion-only Python diffs that never overwrite source files
- recursive Python test-directory scanning
- multiple request analysis across files
- targeted pytest validation in temporary files
- aggregate batch reports
- dry-run analysis
- Newman runtime validation
- optional Postman environment files
- original-failure and healed-pass validation guards

The main example is simple:

```text
OpenAPI requires:  email_address
Test still sends:  userEmail

Safe repair:
userEmail -> email_address
```

The matching decision is deterministic. No LLM decides whether a patch is safe.

---


## Pytest / Requests Adapter

V1.3 added static analysis for simple Python API tests that use the `requests` library. The single-file `pytest analyze` command remains available in V1.4.

Example outdated test:

```python
import requests


def test_create_user() -> None:
    payload = {
        "name": "Test User",
        "userEmail": "qa_user@example.com",
    }

    response = requests.post(
        "http://localhost:3000/users",
        json=payload,
    )

    assert response.status_code == 201
```

The OpenAPI contract requires `email_address`.

The adapter parses the Python file with the standard-library AST. It does not import or execute the test file.

```text
Python test file
        |
        v
AST request and payload parser
        |
        v
NormalizedRequest
        |
        v
OpenAPI path and method resolver
        |
        v
Deterministic drift analyzer
        |
        v
SAFE_PATCH / REJECT
        |
        v
Suggestion-only unified diff
        |
        v
Original Python source unchanged
```

The Python adapter safety rule is:

```text
Detect. Suggest. Never overwrite.
```

Run the example:

```bash
api-drift-healer pytest analyze \
  --file examples/pytest_requests/test_create_user.py \
  --openapi examples/pytest_requests/openapi.yaml
```

Expected result:

```text
Request       : POST /users
Payload fields: name, userEmail
Decision      : SAFE_PATCH
Old field     : userEmail
Required field: email_address
Score         : 0.772
Confidence    : High
```

The CLI prints a unified diff:

```diff
 payload = {
     "name": "Test User",
-    "userEmail": "qa_user@example.com",
+    "email_address": "qa_user@example.com",
 }
```

The diff is only a suggestion. The original Python file is never modified.

Verify the source remains unchanged:

```bash
grep -n "userEmail\|email_address" \
  examples/pytest_requests/test_create_user.py
```

Expected result:

```text
"userEmail": "qa_user@example.com",
```

---

## V1.4 - Multiple Requests and Tests

V1.4 adds a batch pipeline for Python API tests.

Instead of analyzing one file at a time, the CLI can scan a test directory, discover supported `requests` calls, compare each request with OpenAPI, plan safe patches, validate those patches with pytest, and print one aggregate report.

```text
Python test directory
        |
        v
Recursive test-file scanner
        |
        v
Multiple request discovery
        |
        v
OpenAPI path and method matching
        |
        v
Deterministic drift analysis
        |
        v
Safe patch planning
        |
        v
Targeted pytest validation in temporary files
        |
        v
Aggregate batch report
        |
        v
Original Python source files unchanged
```

The batch command only plans patches for `SAFE_PATCH` decisions. Each suggested patch is written to a temporary sibling file and the relevant pytest test function is executed against that temporary file.

The original source file is never overwritten.

Run the included V1.4 example:

```bash
api-drift-healer pytest batch \
  --directory examples/python_batch_v1_4 \
  --openapi examples/python_batch_v1_4/openapi.json \
  --timeout 30
```

Expected report:

```text
Python Batch Report
-------------------
Files scanned: 3
Requests discovered: 3
Requests analyzed: 3
No drift: 2
Drift detected: 1
Safe patch decisions: 1
Rejected drift: 0
Complex drift: 0
Patches generated: 1
Patches validated: 1
Validation failures: 0
Pipeline errors: 0

No source files were changed.
```

The included demo contains:

- two requests that already match OpenAPI
- one request that still sends `userEmail`
- one safe `userEmail -> email_address` patch
- one targeted pytest validation
- zero source-file changes

The V1.4 safety flow is:

```text
Detect. Suggest. Validate. Never overwrite.
```

---

## Postman Adapter

The Postman adapter can read a Postman Collection v2.1 file, locate one request, compare its raw JSON body with OpenAPI, and generate a patched collection.

V1.2 can also execute the original and healed collections with Newman.

```text
Postman collection
        |
        v
Normalized request
        |
        v
OpenAPI path and method resolver
        |
        v
Deterministic drift analyzer
        |
        v
Safe field patch
        |
        v
Temporary healed collection
        |
        v
Newman runtime validation
        |
        v
Validated Postman output
```

The runtime safety rule is:

```text
No Newman PASS, no validated Postman output.
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

Dry-run does not run Newman or write any files.

### Generate a Structurally Healed Collection

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --output create-user.healed.postman_collection.json
```

This command performs static healing only.

The original collection is preserved.

### Validate the Healed Collection with Newman

Start the local demo API:

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

Expected runtime result:

```text
Static analysis: SAFE_PATCH
Candidate: userEmail -> email_address
Original Newman: FAIL (exit code 1)
Healed Newman: PASS
Decision: VALIDATED
```

The final collection is written only after the healed collection passes Newman.

### Optional Environment File

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --environment demo.postman_environment.json \
  --validate-newman
```

### Configure the Newman Timeout

The default timeout is 120 seconds:

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --newman-timeout 45 \
  --validate-newman
```

### Original Collection Guard

By default, validation stops when the original collection already passes Newman.

The guard can be disabled explicitly:

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --allow-original-pass \
  --validate-newman
```

### One-Command Postman Demo

On macOS, Linux, WSL, or Git Bash:

```bash
./scripts/demo_postman.sh
```

From Windows PowerShell:

```powershell
bash scripts/demo_postman.sh
```

The demo:

1. checks Newman and the local API
2. starts the Flask mock server when required
3. proves that the original collection fails Newman
4. detects `userEmail -> email_address`
5. generates a temporary healed collection
6. proves that the healed collection passes Newman
7. writes a validated output
8. verifies that the original collection was preserved
9. removes all temporary files

Expected summary:

```text
Decision: SAFE_PATCH
Original Newman: FAIL
Healed Newman  : PASS
Final decision : VALIDATED
Output policy  : No Newman PASS, no validated output
```

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

### Pytest Runtime Validation

Static Python analysis works with the standard installation.

The V1.4 batch command uses pytest to validate suggested patches in temporary files:

```bash
python -m pip install -e ".[pytest]"
```

The `pytest` extra is required for `api-drift-healer pytest batch`. It is not required for the single-file static `pytest analyze` command.

### Newman Runtime Validation

Python is sufficient for static YAML, Postman, `.http`, and Python requests analysis.

Node.js and Newman are additionally required for Postman runtime validation:

```bash
node --version
newman --version
```

Newman is used only when `--validate-newman` is enabled or when the complete Postman runtime demo is executed.

Verify the CLI:

```bash
api-drift-healer --help
api-drift-healer heal --help
api-drift-healer postman heal --help
api-drift-healer http heal --help
api-drift-healer pytest --help
api-drift-healer pytest analyze --help
api-drift-healer pytest batch --help
```

---



## Pytest / Requests CLI Options

### Analyze One File

```text
--file     Python API test file. Required.
--openapi  OpenAPI YAML or JSON file. Required.
```

Example:

```bash
api-drift-healer pytest analyze \
  --file examples/pytest_requests/test_create_user.py \
  --openapi examples/pytest_requests/openapi.yaml
```

The `analyze` command expects exactly one supported `requests` call and prints a suggested unified diff.

It never writes a modified Python file.

### Analyze and Validate a Directory

```text
--directory  Directory containing Python API test files. Required.
--openapi    OpenAPI YAML or JSON file. Required.
--timeout    Maximum pytest validation time per patch. Default: 30 seconds.
```

Example:

```bash
api-drift-healer pytest batch \
  --directory examples/python_batch_v1_4 \
  --openapi examples/python_batch_v1_4/openapi.json \
  --timeout 30
```

The `batch` command:

- recursively scans supported Python test files
- discovers every supported request call
- analyzes each request against OpenAPI
- plans only deterministic safe patches
- validates each planned patch with targeted pytest execution
- prints an aggregate report
- never changes the original source files

Exit behavior:

```text
0  The batch completed without pipeline errors or validation failures.
1  A pipeline error occurred, pytest was unavailable, or a patch validation failed.
2  Typer rejected invalid CLI input or a required path was missing.
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
--collection           Postman Collection v2.1 JSON file. Required.
--request              Exact Postman request name. Required.
--openapi              OpenAPI YAML or JSON file. Required.
--output               Path for the healed or validated collection.
--dry-run              Show the static decision and diff without writing.
--overwrite            Replace an existing output file.
--validate-newman      Validate the original and healed collections with Newman.
--environment          Optional Postman environment file for Newman.
--newman-timeout       Maximum Newman runtime in seconds. Default: 120.
--allow-original-pass  Continue when the original collection already passes.
```

Validation-related combinations:

```text
--environment requires --validate-newman
--allow-original-pass requires --validate-newman
--dry-run cannot be combined with --validate-newman
```

Exit codes:

```text
0  Dry-run succeeded, healed output generated, validated output generated,
   or no drift was found

1  Patch rejected, original collection unexpectedly passed,
   or the healed collection failed Newman

2  Invalid input, unsupported format, unsafe output path,
   Newman missing, Newman timeout, or another tooling error
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

For Python requests tests:

```text
Detect. Suggest. Never overwrite.
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



### Pytest / Python Requests

- Python files parsed with the standard-library AST
- `requests.post`, `requests.put`, and `requests.patch`
- literal URL strings passed positionally or with `url=`
- literal JSON-compatible dictionaries
- named payload variables passed with `json=payload`
- inline dictionaries passed with `json={...}`
- exact OpenAPI path and HTTP method matching
- one top-level field rename per request
- deterministic safety scoring
- unified source diffs
- single- and double-quote preservation
- UTF-8 and UTF-8 BOM source files
- source-file protection
- suggestion-only behavior
- recursive discovery of `test_*.py` and `*_test.py`
- nested test directories
- multiple supported requests across files
- multiple supported requests inside one file
- pytest test-function and line-number context
- safe per-request patch planning
- targeted pytest validation in temporary files
- validation timeout and tooling-error handling
- temporary-file cleanup
- aggregate batch reporting

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
- original collection execution with Newman
- temporary healed collection execution with Newman
- original-failure validation guard
- healed-pass output requirement
- optional Postman environment forwarding
- configurable Newman timeout
- validated output protection
- cross-platform Newman executable discovery
- Windows `.cmd` shim support

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

### Pytest / Python Requests

The Python adapter is intentionally suggestion-only. It never overwrites a Python source file.

The single-file `pytest analyze` command expects exactly one supported request call. The V1.4 `pytest batch` command scans multiple files and analyzes every supported request it discovers.

It does not currently support:

- automatic Python source rewrites
- dynamic or f-string request URLs
- payloads returned by functions
- fixture-generated payloads
- dynamic values inside payload dictionaries
- `requests.Session`
- `requests.request`
- `httpx`
- async HTTP clients
- nested JSON field repairs
- multiple field repairs in one request
- OpenAPI path-template matching
- OpenAPI `$ref`, `allOf`, `oneOf`, or `anyOf` request schemas
- combining multiple patches into one rewritten source file
- automatic Pull Request creation for Python tests

Unsupported patterns are rejected or skipped. Python files are never imported or executed during static analysis. Only temporary suggested files are executed during targeted pytest validation.

### `.http` Files

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

### Postman

The Postman adapter does not currently support:

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
- healing multiple Postman requests in one run
- isolated Newman execution for only the selected request
- automatic Postman Pull Request creation

One Postman request is selected and patched per healing run.

Newman executes the collection containing that request. The tool does not yet heal multiple requests in one run or isolate Newman execution to only the selected request.

The original collection must fail Newman by default, and the temporarily healed collection must pass before a validated output is written.

---

## Architecture

```text
Input Adapter
    |
    v
NormalizedRequest
    |
    v
OpenAPI Resolver
    |
    v
ResolvedRequestSchema
    |
    v
Deterministic Drift Analyzer
    |
    v
SAFE_PATCH / REJECT / NO_DRIFT / COMPLEX_DRIFT
    |
    +------------------------------+
    |                              |
    v                              v
Format-specific Patcher      Python Diff Builder
    |                              |
    v                              v
Optional Runtime Validator   Suggestion-only Diff
    |                              |
    v                              v
Validated Output             Source Unchanged
```

Runtime validation is optional and format-specific.

The Python adapter stops at suggestion and validation. It does not write a healed Python source file. The V1.4 batch pipeline validates suggested patches in temporary files and deletes those files after execution.

The deterministic drift analyzer remains independent from Newman, Postman, `.http`, YAML, and Python source formats.

This makes it possible to add other adapters without rebuilding the safety engine.

---

## Project Structure

```text
api-drift-healer-demo/
|-- api_drift_healer/
|   |-- adapters/
|   |   |-- __init__.py
|   |   |-- http_file.py
|   |   `-- postman.py
|   |-- __init__.py
|   |-- cli.py
|   |-- drift_analyzer.py
|   |-- http_healer.py
|   |-- models.py
|   |-- newman_runner.py
|   |-- openapi_resolver.py
|   |-- postman_healer.py
|   |-- postman_validator.py
|   |-- python_batch_analyzer.py
|   |-- python_batch_patch_planner.py
|   |-- python_batch_report.py
|   |-- python_batch_scanner.py
|   |-- python_batch_validator.py
|   |-- python_diff.py
|   |-- python_parser.py
|   |-- python_patch_validator.py
|   |-- python_request_analyzer.py
|   `-- python_test_scanner.py
|-- examples/
|   |-- basic_yaml/
|   |-- http/
|   |-- postman/
|   |-- pytest_requests/
|   `-- python_batch_v1_4/
|       |-- openapi.json
|       |-- test_create_second_user.py
|       |-- test_create_user_current.py
|       `-- test_create_user_drift.py
|-- scripts/
|-- tests/
|-- auto_healer.py
|-- field_matcher.py
|-- mock_server.py
|-- pyproject.toml
`-- README.md
```

---

## Automated Tests

Run all tests:

```bash
python -m unittest discover
```

Current V1.4 test suite:

```text
234 automated tests
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
- cross-platform Newman executable discovery
- original and healed Newman execution
- Postman environment forwarding
- Newman timeout and tooling error handling
- original-failure validation guard
- healed-pass output requirement
- validated Postman output protection
- real Flask and Newman runtime demo
- Python AST request and payload parsing
- literal payload value extraction
- full URL to OpenAPI path mapping
- Python request OpenAPI analysis
- safe Python field-rename decisions
- suggestion-only unified Python diffs
- key-only token replacement
- single- and double-quote preservation
- unsafe Python patch rejection
- Python CLI behavior
- Python source-file preservation
- recursive Python test-directory scanning
- nested test-file discovery and exclusion rules
- multiple request extraction across files
- test-function and line-number context
- batch OpenAPI request analysis
- safe batch patch planning
- targeted pytest subprocess validation
- validation timeout and missing-pytest handling
- temporary-file cleanup
- aggregate batch reporting
- Pytest batch CLI behavior
- UTF-8 BOM parsing and patch generation

---

## Current Status

```text
V0.4 DONE Deterministic smart field matching
V0.5 DONE Installable Typer CLI
V0.6 DONE Runnable YAML example and one-command demo

V1.0 DONE Format-independent request model
V1.0 DONE Postman Collection v2.1 parser
V1.0 DONE Nested request discovery
V1.0 DONE OpenAPI path and method resolver
V1.0 DONE Format-independent drift analyzer
V1.0 DONE Safe Postman body patcher
V1.0 DONE Healed collection writer
V1.0 DONE Postman dry-run and diff
V1.0 DONE Postman CLI
V1.0 DONE One-command Postman demo

V1.1 DONE Single-request `.http` parser
V1.1 DONE Method, URL, path, and JSON body extraction
V1.1 DONE LF and CRLF newline preservation
V1.1 DONE Multiple-request safety rejection
V1.1 DONE Format-preserving top-level field patcher
V1.1 DONE HTTP healing service
V1.1 DONE `.http` dry-run and source diff
V1.1 DONE `.http` CLI
V1.1 DONE Separate healed `.http` output
V1.1 DONE One-command HTTP demo
V1.1 DONE 153 automated tests
V1.2 DONE Cross-platform Newman executable discovery
V1.2 DONE Original collection runtime execution
V1.2 DONE Temporary healed collection validation
V1.2 DONE Original-failure guard
V1.2 DONE Healed-pass requirement
V1.2 DONE Optional Postman environment support
V1.2 DONE Configurable Newman timeout
V1.2 DONE Validated output protection
V1.2 DONE Newman validation CLI options
V1.2 DONE Real Flask and Newman runtime demo
V1.2 DONE Windows, macOS, and Linux runner support
V1.2 DONE 179 automated tests

V1.3 DONE Python AST request and payload parser
V1.3 DONE `requests.post`, `requests.put`, and `requests.patch` detection
V1.3 DONE Literal URL and JSON-compatible payload extraction
V1.3 DONE OpenAPI path and method mapping
V1.3 DONE Existing deterministic safety engine reuse
V1.3 DONE Suggestion-only unified Python diff
V1.3 DONE Quote-style preservation
V1.3 DONE Python source-file protection
V1.3 DONE Pytest / Requests CLI
V1.3 DONE Runnable Python example
V1.3 DONE 198 automated tests

V1.4 DONE Recursive Python test-directory scanner
V1.4 DONE Multiple request discovery across files
V1.4 DONE Multiple request discovery inside one file
V1.4 DONE Test-function and line-number context
V1.4 DONE Batch OpenAPI request analysis
V1.4 DONE Safe per-request patch planning
V1.4 DONE Targeted pytest patch validation
V1.4 DONE Temporary-file validation without source changes
V1.4 DONE Validation timeout and tooling-error handling
V1.4 DONE Aggregate batch report
V1.4 DONE Pytest batch CLI command
V1.4 DONE UTF-8 BOM parsing and patch generation
V1.4 DONE Runnable multi-test Python example
V1.4 DONE 234 automated tests
```

---

## Roadmap


### V1.5 - Multi-Adapter Batch Runs

- support multiple requests in `.http` inputs
- support multiple Postman requests in one healing run
- produce combined reports across writable adapters
- reject ambiguous cross-request patches

### V2 - CI Integration

- run inside GitHub Actions
- react to failed API tests
- generate reports or Pull Requests
- keep human review before merge

### V3 - Local LLM Explanation Layer

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
