# API Drift Healer 🛠️

API Drift Healer is a local Python prototype that fixes a small but annoying API testing problem:

Your OpenAPI spec changes, but your YAML test case still sends the old request field.

In this demo, the API now expects `email_address`, but the test still sends `userEmail`.  
The original test fails with `400`, the healer patches the field, reruns the healed test, generates a readable report, and can optionally open a GitHub Pull Request.

> 🛑 **Golden Rule: No PASS, No PR.**
>
> The tool does not open a Pull Request just because it generated a patch.  
> It only moves forward after the healed test passes locally.

---

## The Problem: API Contract Drift

API tests often fail because the API contract changed, but the test data did not.

Example:

- **OpenAPI requires:** `email_address`
- **Outdated test sends:** `userEmail`
- **Result:**

```text
[FAIL] Expected 201, got 400
Error: missing required field: email_address
```

That mismatch is the contract drift this prototype is designed to catch and heal.

---

## What This Prototype Does

API Drift Healer compares a YAML-based API test case with the OpenAPI contract.

For the current demo, it can:

- run the original test
- detect that the test fails
- compare the request body with the OpenAPI schema
- find the outdated field
- generate a healed test file
- rerun the healed test locally
- generate `heal_report.md`
- optionally open a human-reviewable GitHub Pull Request

Current supported demo fix:

```text
userEmail -> email_address
```

This is intentionally small.  
The goal is to prove the core loop before expanding into more formats and more complex drift cases.

---

## Demo Flow

```text
Original test FAIL
        ↓
OpenAPI contract drift detected
        ↓
Outdated field patched
        ↓
Healed test generated
        ↓
Healed test PASS
        ↓
heal_report.md generated
        ↓
Optional GitHub PR created
```

The important part is not just generating a patch.

The important part is proving the patch works.

---

## Project Structure

```text
api-drift-healer-demo/
├── mock_server.py
├── openapi.yaml
├── api_test_case.yaml
├── test_runner.py
├── auto_healer.py
├── requirements.txt
└── .gitignore
```

---

## Core Files

### `mock_server.py`

A small local Flask API server used for the demo.

It exposes:

```text
POST /users
```

The server expects this request field:

```json
{
  "email_address": "qa_user@example.com"
}
```

If `email_address` is missing, the server returns `400`.

---

### `openapi.yaml`

The source of truth for the API contract.

It defines `email_address` as a required request field:

```yaml
required:
  - email_address
```

---

### `api_test_case.yaml`

The intentionally outdated API test case.

It still sends the old field:

```yaml
body:
  name: Test User
  userEmail: qa_user@example.com
```

This test is expected to fail before the healer runs.

---

### `test_runner.py`

A lightweight Python API test runner.

It reads the YAML test case, sends the HTTP request, and compares the actual status code with the expected status code.

Example failure:

```text
[FAIL] Expected 201, got 400
```

Example success:

```text
[PASS] Expected 201, got 201
```

---

### `auto_healer.py`

The main drift healer.

It runs the full local flow:

1. runs the original test
2. detects failure
3. compares the test request body with the OpenAPI schema
4. finds the outdated field
5. generates a healed test file
6. reruns the healed test
7. generates `heal_report.md`
8. optionally opens a GitHub Pull Request

---

## Requirements

- Python 3.10+
- Flask
- PyYAML
- requests
- GitHub CLI, only for PR mode

Install dependencies:

```bash
pip install -r requirements.txt
```

If `requirements.txt` is not available:

```bash
pip install Flask PyYAML requests
```

For PR mode, install and authenticate GitHub CLI:

```bash
gh auth login
```

---

## Quick Start

### 1. Create and activate a virtual environment

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

---

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Start the mock API server

Open a terminal and run:

```bash
python mock_server.py
```

The server runs on:

```text
http://localhost:3000
```

Keep this terminal open.

---

### 4. Run API Drift Healer

Open another terminal and run:

```bash
python auto_healer.py
```

Expected flow:

```text
=== API DRIFT HEALER V0.3 (EXPLAINABLE SECURE PR FLOW) ===

[1] Running the original test case...
[FAIL] Expected 201, got 400

[!] Test FAILED! Triggering Healer...

[+] Drift Match Detected: 'userEmail' -> 'email_address'
[+] Healed test file generated for demo: api_test_case.healed.yaml

[3] Automatically validating the healed test case...
[PASS] Expected 201, got 201

[4] Generating explainability report...
[+] Heal report generated: heal_report.md

[5] PR creation skipped for local V0.3 report test.
```

By default, the tool runs in local report mode and does not open a Pull Request.

---

## Local Report Mode

Default behavior:

```bash
python auto_healer.py
```

This mode:

- runs the original failing test
- detects API contract drift
- generates the healed test file
- validates the healed test
- generates `heal_report.md`
- skips PR creation

This is useful for local testing, demos, and debugging.

---

## GitHub PR Mode

To enable Pull Request creation, set `CREATE_PR=true`.

### Windows PowerShell

```powershell
$env:CREATE_PR="true"
python auto_healer.py
```

After the run, clear the environment variable:

```powershell
Remove-Item Env:CREATE_PR
```

### macOS / Linux

```bash
CREATE_PR=true python auto_healer.py
```

PR mode requires:

- GitHub CLI installed
- GitHub CLI authenticated
- clean working tree
- healed test must pass locally

If the working tree is not clean, the PR flow stops before creating a branch.

This is intentional.  
The tool should not create fix branches while unrelated local changes are sitting around like tiny landmines.

---

## Example Generated Report

After a successful heal, API Drift Healer generates:

```text
heal_report.md
```

Example:

```md
# API Drift Healer Report

## Summary
API Drift Healer detected a contract drift, generated a safe patch, validated the healed test locally, and prepared a human-reviewable report for the fix.

## Test
`Create User - Success`

## Root Cause
OpenAPI requires `email_address`, but the test case was sending `userEmail`.

## Applied Fix
`userEmail` -> `email_address`

## Validation
- Original test: Failed with `400`
- Expected status: `201`
- Healed test: Passed with `201`

## Confidence
`High`

## Confidence Reason
Exactly one missing required field and one invalid existing field were found. The field match passed the semantic safety guard and the healed test passed locally.

## Files
- Original test file: `api_test_case.yaml`
- Healed test file: `api_test_case.healed.yaml`
- OpenAPI contract: `openapi.yaml`

## Safety
This report was generated only after the healed test passed locally.

No PASS, No PR.
```

---

## Example Pull Request

When PR mode is enabled, the tool opens a reviewable PR with:

- root cause
- applied fix
- validation result
- confidence level
- safety rule

Example PR title:

```text
Auto-heal API test drift: userEmail -> email_address
```

Example diff:

```diff
body:
  name: Test User
- userEmail: qa_user@example.com
+ email_address: qa_user@example.com
```

The bot does not merge anything automatically.

A human reviews the PR.

---

## Safety Principles

API Drift Healer follows these rules:

```text
No PASS, No PR.
No direct push to main.
No blind overwrite.
No auto-merge.
Human review stays in the loop.
```

The current prototype only applies a patch when the drift is simple and safe:

```text
1 missing required field
+
1 invalid existing field
+
semantic safety guard passed
+
healed test passed locally
```

If the drift is complex, ambiguous, or risky, the tool stops.

That is a feature, not a bug.  
A cautious bot is annoying. A confident wrong bot is expensive.

---

## Current Status

```text
V0   ✅ Core local heal proof
V0.1 ✅ One-command FAIL -> HEAL -> PASS flow
V0.2 ✅ Secure PR flow after local validation
V0.3 ✅ Explainability report generation
V0.3.1 ✅ CREATE_PR toggle and clean working tree guard
```

---

## Roadmap

### V0.4 — Smarter Field Matching

Support more field rename patterns:

```text
firstName -> first_name
lastName -> last_name
phoneNumber -> phone_number
userId -> user_id
createdAt -> created_at
```

Planned improvements:

- normalize camelCase and snake_case
- compare field tokens
- use OpenAPI type and format metadata
- avoid unsafe mappings

---

### V0.5 — CLI Arguments

Move from hardcoded file names to CLI usage:

```bash
api-drift-healer heal \
  --test api_test_case.yaml \
  --openapi openapi.yaml
```

Possible options:

```text
--test
--openapi
--output
--apply
--create-pr
--dry-run
```

---

### V1 — Postman Adapter

Support Postman collections.

Goal:

```text
Postman collection
      ↓
Normalized test case
      ↓
Core drift engine
      ↓
Patched Postman collection
```

---

### V1.1 — VS Code `.http` Adapter

Support REST Client / `.http` files.

Example:

```http
POST http://localhost:3000/users
Content-Type: application/json

{
  "name": "Test User",
  "userEmail": "qa_user@example.com"
}
```

Healed:

```http
POST http://localhost:3000/users
Content-Type: application/json

{
  "name": "Test User",
  "email_address": "qa_user@example.com"
}
```

---

### V1.2 — Pytest / Requests Adapter

Detect outdated payload fields inside Python API tests.

Initial goal:

- find simple payload dictionaries
- match request URL and method
- generate suggested patches
- avoid risky automatic rewrites

---

### V2 — GitHub Actions Integration

Run API Drift Healer inside CI.

Possible flow:

```text
CI test fails
      ↓
API Drift Healer checks OpenAPI
      ↓
Healed test passes
      ↓
Bot opens PR or comments on an existing PR
```

---

### V3 — Local LLM Explanation Layer

LLMs may be useful later, but not as blind patch engines.

Planned rule:

```text
AI explains the fix.
Tests prove the fix.
```

In other words:

- deterministic code makes the patch
- tests validate the patch
- AI may help explain the patch

Because letting an LLM freestyle-edit test files is how YAML becomes modern art.

---

## What This Is Not

API Drift Healer is not:

- a full AI testing platform
- a replacement for QA engineers
- a production-ready enterprise product
- a universal API test repair tool
- a blind auto-fix bot

It is currently a focused local-first prototype for one painful problem:

> API contract drift breaking API tests.

---

## Why Local-First?

The current prototype runs locally.

No cloud payload sharing.  
No API keys required.  
No OpenAI dependency.  
No remote test data processing.

This makes it easier to reason about safety and trust during early development.

---

## Demo Summary

```text
OpenAPI requires:
email_address

Test sends:
userEmail

Original test:
400 FAIL

Healer applies:
userEmail -> email_address

Healed test:
201 PASS

Report:
Generated

PR:
Optional, human-reviewable
```

---

## License

MIT
