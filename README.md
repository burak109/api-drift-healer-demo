# API Drift Healer 🛠️

**Current release: V0.5 — Installable Typer CLI**

Detect OpenAPI contract drift.

Heal outdated YAML API tests.

Validate every proposed repair locally.

Optionally apply the validated fix or open a human-reviewable GitHub Pull Request.

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

## What It Does

API Drift Healer compares an OpenAPI contract with a YAML API test case and detects outdated request fields.

It:

- runs the original API test
- detects a possible field rename
- rejects ambiguous or unsafe matches
- generates a healed test case
- reruns the healed test locally
- allows apply or PR operations only after validation passes

## Basic Example

The OpenAPI contract requires:

```text
email_address
```

But the test still sends:

```text
userEmail
```

API Drift Healer proposes:

```text
userEmail -> email_address
```

And validates the result:

```text
Original test: 400 FAIL
Healed test:   201 PASS
```

A complete runnable example is available here:

[`examples/basic_yaml`](examples/basic_yaml/README.md)

---

## What V0.5 Adds

V0.5 turns the prototype into an installable command-line tool.

It adds:

- a Typer-based CLI
- `--test` and `--openapi` file arguments
- optional custom output paths
- a real `--dry-run` mode
- a validated `--apply` mode
- `--create-pr` flag validation
- reusable healer execution logic
- installable `api-drift-healer` command
- CLI test coverage
- support for running outside the repository directory with absolute paths

---

## Current Limitations

API Drift Healer intentionally supports a narrow and cautious healing scope.

### Currently Supported

- YAML API test cases
- one missing required OpenAPI field
- one invalid existing request field
- deterministic field rename detection
- local validation of the healed test
- optional apply and GitHub Pull Request flows after validation

The supported automatic-healing scenario is:

```text
1 missing required OpenAPI field
+
1 invalid existing request field
```

### Not Supported Yet

- Postman collections
- multiple simultaneous field repairs
- nested object or array repairs
- automatic CI pipeline integration
- AI-generated patches
- healing without local validation

The tool stops when:

- multiple required fields are missing
- multiple invalid request fields exist
- the candidate mapping is ambiguous
- semantic qualifiers conflict
- OpenAPI type or format checks fail
- the score is below the safety threshold
- a hard safety conflict is detected
- the healed test does not pass

A cautious tool may stop more often.

A confident but incorrect tool can silently damage tests.

---

## Example Safe Matches

```text
userEmail   -> email_address
phoneNumber -> phone_number
legacyCode  -> legacy_code
```

These candidates may be accepted when their semantic, type, format, and safety checks agree.

---

## Example Rejected Matches

```text
displayName -> email_address
firstName   -> last_name
userId      -> customer_id
```

Common rejection reasons:

- no shared semantic concept
- incompatible OpenAPI type
- incompatible OpenAPI format
- conflicting qualifiers
- no strong matching anchor
- score below the safety threshold
- hard safety conflict

---

## Installation

### Requirements

- Python 3.10 or newer
- GitHub CLI only for Pull Request mode

Clone the repository:

```bash
git clone https://github.com/burak109/api-drift-healer-demo.git
cd api-drift-healer-demo
```

Create and activate a virtual environment.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project in editable mode:

```bash
python -m pip install -e .
```

This installs the project dependencies and creates the command:

```text
api-drift-healer
```

Verify the installation:

```bash
api-drift-healer --help
api-drift-healer heal --help
```

---

## Quick Start

### 1. Install the CLI

From the repository root:

```bash
python -m pip install -e .
```

### 2. Start the mock API

Open the first terminal:

```bash
python mock_server.py
```

The demo server runs at:

```text
http://localhost:3000
```

Keep this terminal open.

### 3. Preview the repair

Open a second terminal in the repository root:

```bash
api-drift-healer heal \
  --test examples/basic_yaml/api_test_case.yaml \
  --openapi examples/basic_yaml/openapi.yaml \
  --dry-run
```

Expected result:

```text
Original test: 400 FAIL
Candidate: userEmail -> email_address
Decision: SAFE PATCH
No files were changed.
```

### 4. Generate and validate the healed test

```bash
api-drift-healer heal \
  --test examples/basic_yaml/api_test_case.yaml \
  --openapi examples/basic_yaml/openapi.yaml \
  --output examples/basic_yaml/api_test_case.healed.yaml
```

Expected validation result:

```text
Original test: 400 FAIL
Healed test:   201 PASS
```

Generated files:

```text
examples/basic_yaml/api_test_case.healed.yaml
examples/basic_yaml/heal_report.md
```

The original test file is not modified in the default heal mode.

For `--apply`, `--create-pr`, and other options, see the CLI Options section below.

A focused walkthrough is also available in:

[`examples/basic_yaml/README.md`](examples/basic_yaml/README.md)

---

## CLI Options

```text
--test       Path to the YAML API test file. Required.
--openapi    Path to the OpenAPI contract file. Required.
--output     Custom path for the generated healed test file.
--dry-run    Analyze drift without writing files.
--apply      Apply the validated patch to the original test file.
--create-pr  Open a Pull Request after a validated apply.
```

Invalid combinations are rejected:

```text
--dry-run + --apply
--create-pr without --apply
```

---

## Workflow

```text
Original test runs
        ↓
Original test FAILS
        ↓
OpenAPI schema is loaded
        ↓
Missing and invalid fields are identified
        ↓
Candidate rename is evaluated
        ↓
SAFE PATCH or REJECT
        ↓
Healed test is generated only if safe
        ↓
Healed test runs locally
        ↓
Healed test PASSES
        ↓
heal_report.md is generated
        ↓
Optional validated apply
        ↓
Optional GitHub Pull Request
        ↓
Human review
```

The tool never treats patch generation alone as success.

---

## Project Structure

```text
api-drift-healer-demo/
├── api_drift_healer/
│   ├── __init__.py
│   └── cli.py
├── examples/
│   └── basic_yaml/
│       ├── README.md
│       ├── openapi.yaml
│       └── api_test_case.yaml
├── mock_server.py
├── openapi.yaml
├── api_test_case.yaml
├── test_runner.py
├── auto_healer.py
├── field_matcher.py
├── test_field_matcher.py
├── test_auto_healer.py
├── test_cli.py
├── pyproject.toml
├── requirements.txt
├── README.md
└── .gitignore
```

The files under `examples/basic_yaml/` provide the recommended runnable demo.

Generated files such as `api_test_case.healed.yaml` and `heal_report.md` are ignored by Git.

---

## Core Files

### `api_drift_healer/cli.py`

The Typer command-line interface.

It:

- validates CLI arguments
- resolves input and output paths
- selects the execution mode
- rejects unsafe flag combinations
- calls the reusable healer engine
- returns the engine exit code

### `auto_healer.py`

The orchestration layer.

It:

- runs the original test
- loads the OpenAPI schema
- identifies candidate drift
- calls the deterministic matcher
- generates the healed test
- validates the healed test
- creates the report
- optionally applies the validated patch
- optionally starts the Pull Request flow

### `field_matcher.py`

The deterministic safety engine.

It performs:

- field-name normalization
- semantic concept extraction
- qualifier conflict detection
- value-type detection
- value-format detection
- OpenAPI type compatibility checks
- OpenAPI format compatibility checks
- string similarity calculation
- deterministic weighted scoring
- hard conflict rejection

The current safety threshold is:

```text
0.700
```

### `test_runner.py`

A small YAML-based API test runner.

It loads a test case, sends the configured request, and compares the actual status with the expected status.

### `mock_server.py`

A local Flask API used by the demo.

It exposes:

```text
POST /users
```

The server expects `email_address` and returns `400` when the field is missing.

---

## Explainability Report

After a successful validated heal, the tool generates:

```text
heal_report.md
```

The report includes:

- root cause
- candidate field rename
- applied fix
- original test result
- healed test result
- match score
- safety threshold
- confidence
- matching evidence
- conflict reasons
- involved files
- safety statement

Example summary:

```text
Root cause:
OpenAPI requires email_address, but the test sends userEmail.

Applied fix:
userEmail -> email_address

Validation:
Original test: 400 FAIL
Healed test: 201 PASS

Decision:
SAFE PATCH
```

---

## Pull Request Safety

The Pull Request workflow follows these rules:

```text
No PASS, no PR.
No direct push to main.
No blind overwrite.
No auto-merge.
Human review stays in the loop.
```

The tool checks for a clean working tree before creating a branch.

This prevents unrelated local changes from being mixed into the generated fix.

The bot opens a reviewable Pull Request but does not merge it.

---

## Automated Tests

Run the complete test suite:

```bash
python -m unittest -v \
  test_field_matcher.py \
  test_auto_healer.py \
  test_cli.py
```

Current suite:

```text
45 matcher unit tests
+
3 healer integration tests
+
8 CLI tests
=
56 automated tests
```

Expected result:

```text
Ran 56 tests

OK
```

The CLI tests cover:

- main help output
- required CLI options
- invalid flag combinations
- default heal mode
- dry-run mode
- apply mode
- custom output forwarding
- engine argument forwarding

---

## Current Status

```text
V0     ✅ Core local heal proof
V0.1   ✅ One-command FAIL -> HEAL -> PASS flow
V0.2   ✅ Secure PR flow after local validation
V0.3   ✅ Explainability report generation
V0.3.1 ✅ CREATE_PR toggle and clean working tree guard
V0.4   ✅ Safe smart field matching
V0.4   ✅ Semantic, qualifier, type, and format checks
V0.4   ✅ Deterministic scoring and hard conflict rejection
V0.4   ✅ 48 automated tests
V0.5   ✅ Installable Typer CLI
V0.5   ✅ File path arguments
V0.5   ✅ Dry-run mode
V0.5   ✅ Validated apply mode
V0.5   ✅ CLI flag validation
V0.5   ✅ Custom output support
V0.5   ✅ 56 automated tests
```

---

## Roadmap

### V1 — Postman Adapter

Support Postman collections.

Target flow:

```text
Postman collection
        ↓
Normalized internal test model
        ↓
Core drift engine
        ↓
Patched Postman collection
```

### V1.1 — VS Code `.http` Adapter

Support REST Client and `.http` request files.

### V1.2 — Pytest / Requests Adapter

Detect outdated payload fields inside Python API tests.

Initial goals:

- locate simple request payload dictionaries
- associate payloads with request URLs and methods
- generate suggested patches
- preserve surrounding test logic
- reject risky automatic rewrites

### V2 — GitHub Actions Integration

Run API Drift Healer inside CI.

Possible flow:

```text
CI test fails
        ↓
API Drift Healer reads OpenAPI
        ↓
Candidate patch is evaluated
        ↓
Healed test passes
        ↓
Bot opens a PR or comments on an existing PR
```

### V3 — Local LLM Explanation Layer

A local LLM may help explain deterministic decisions later.

Planned rule:

```text
Deterministic code decides.
Tests validate.
AI explains.
Humans review.
```

The LLM would not be trusted as the patch engine.

---

## What This Is Not

API Drift Healer is not:

- a complete API testing platform
- a replacement for QA engineers
- a production-ready enterprise product
- a universal test-repair system
- a blind AI auto-fix bot
- a tool that automatically merges changes
- a guarantee that every API drift can be healed

It is a focused local-first prototype for one specific problem:

> API contract drift breaking API tests.

---

## Why Local-First?

The current prototype runs locally.

It does not require:

- cloud payload sharing
- OpenAI API access
- remote test-data processing
- external AI services
- API keys for local analysis

GitHub authentication is only required for Pull Request mode.

---

## License

MIT