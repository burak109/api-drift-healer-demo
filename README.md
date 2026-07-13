# API Drift Healer 🛠️

**Current release: V0.4 - Safe Smart Field Matching**

API Drift Healer is a local-first Python prototype that detects contract drift between an OpenAPI specification and a YAML-based API test case.

In the demo scenario, the API contract expects:

```text
email_address
```

But the outdated test still sends:

```text
userEmail
```

The original test fails with `400`. API Drift Healer evaluates the possible field rename using deterministic semantic, type, format, qualifier, and similarity checks.

It only generates a patch when the candidate passes the safety rules.

The healed test is then rerun locally, documented in a readable report, and can optionally be submitted as a human-reviewable GitHub Pull Request.

> 🛑 **Golden Rule: No PASS, No PR.**
>
> Generating a patch is not enough.
>
> The healed test must pass locally before the tool can open a Pull Request.

---

## The Problem: API Contract Drift

API contracts change.

Tests often do not change at the same time.

Example:

- **OpenAPI requires:** `email_address`
- **Outdated test sends:** `userEmail`
- **Original result:** `400 Bad Request`

```text
[FAIL] Expected 201, got 400
Error: missing required field: email_address
```

This mismatch is API contract drift.

A developer could fix it manually, but repetitive contract changes create noisy failures and consume review time.

API Drift Healer demonstrates a safer workflow:

```text
detect
→ evaluate
→ patch
→ validate
→ explain
→ request human review
```

---

## What This Prototype Does

API Drift Healer compares a YAML API test case with an OpenAPI request schema.

The current version can:

- run the original API test
- detect that the test fails
- read the OpenAPI request schema
- identify one missing required field
- identify one invalid request-body field
- normalize different field naming styles
- extract semantic concepts from field names
- detect conflicting field qualifiers
- validate the source value against the target OpenAPI type
- validate the source value against the target OpenAPI format
- calculate normalized field-name similarity
- calculate a deterministic field-match score
- reject unsafe or ambiguous candidate mappings
- generate a healed test file only when the candidate is safe
- rerun the healed test locally
- generate an explainability report
- optionally open a GitHub Pull Request

---

## Current V0.4 Scope

V0.4 intentionally supports a narrow automatic-healing scenario:

```text
1 missing required OpenAPI field
+
1 invalid existing request field
```

The tool does not attempt a blind rewrite when multiple fields are missing, multiple invalid fields exist, or the candidate mapping is ambiguous.

This constraint is deliberate.

A cautious tool may stop more often.

A confident wrong tool can silently damage tests.

---

## Example Safe Matches

```text
userEmail   -> email_address
phoneNumber -> phone_number
legacyCode  -> legacy_code
```

These candidates can be accepted when their semantic, type, format, and safety checks agree.

---

## Example Rejected Matches

```text
displayName -> email_address
firstName   -> last_name
userId      -> customer_id
```

Examples of rejection reasons:

- no shared semantic concept
- incompatible OpenAPI format
- incompatible OpenAPI type
- conflicting qualifiers
- no strong matching anchor
- score below the safety threshold
- hard safety conflict

A numerical score cannot override a hard conflict.

---

## Demo Flow

```text
Original test FAIL
        ↓
OpenAPI contract drift detected
        ↓
One candidate field rename identified
        ↓
Field names normalized
        ↓
Semantic concepts compared
        ↓
Qualifiers checked
        ↓
OpenAPI type checked
        ↓
OpenAPI format checked
        ↓
Deterministic score calculated
        ↓
SAFE PATCH or REJECT
        ↓
Healed test generated only if safe
        ↓
Healed test rerun locally
        ↓
Healed test PASS
        ↓
heal_report.md generated
        ↓
Optional GitHub Pull Request
        ↓
Human review
```

The tool does not consider a generated patch successful until the healed test passes.

---

## Project Structure

```text
api-drift-healer-demo/
├── mock_server.py
├── openapi.yaml
├── api_test_case.yaml
├── test_runner.py
├── auto_healer.py
├── field_matcher.py
├── test_field_matcher.py
├── test_auto_healer.py
├── requirements.txt
└── .gitignore
```

Generated files such as the healed test and report may be ignored by Git depending on the `.gitignore` configuration.

---

## Core Files

### `mock_server.py`

A small local Flask API used by the demo.

It exposes:

```text
POST /users
```

The server expects a request body containing:

```json
{
  "name": "Test User",
  "email_address": "qa_user@example.com"
}
```

If `email_address` is missing, the server returns `400`.

---

### `openapi.yaml`

The source of truth for the API contract.

It defines `email_address` as a required request property:

```yaml
required:
  - email_address
```

The schema also defines its type and format:

```yaml
email_address:
  type: string
  format: email
```

---

### `api_test_case.yaml`

The intentionally outdated API test case.

It sends:

```yaml
body:
  name: Test User
  userEmail: qa_user@example.com
```

The test is expected to fail before healing because the API now requires `email_address`.

---

### `test_runner.py`

A lightweight YAML-based API test runner.

It:

1. loads a test case
2. sends the configured HTTP request
3. compares the actual status with the expected status
4. prints a PASS or FAIL result

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

The main orchestration layer.

It runs the complete workflow:

1. runs the original test
2. stops when the original test already passes
3. reads the OpenAPI request schema
4. identifies the missing and invalid fields
5. sends the candidate rename to `field_matcher.py`
6. stops when the matcher rejects the candidate
7. generates a healed test file for a safe candidate
8. reruns the healed test locally
9. stops when the healed test fails
10. generates `heal_report.md`
11. optionally starts the secure PR workflow

It also protects the PR flow with a clean-working-tree guard.

---

### `field_matcher.py`

The deterministic V0.4 field-matching engine.

It performs:

- field-name normalization
- semantic concept extraction
- qualifier conflict detection
- runtime value-type detection
- runtime value-format detection
- OpenAPI type compatibility checks
- OpenAPI format compatibility checks
- normalized string similarity calculation
- deterministic weighted scoring
- hard conflict rejection

The current safety threshold is:

```text
0.700
```

The threshold is only one part of the decision.

A candidate can still be rejected above the threshold when a hard safety conflict exists.

Examples:

```text
firstName -> last_name
userId -> customer_id
displayName -> email_address
```

The matcher returns a structured decision containing:

- score
- threshold
- confidence
- safe or rejected state
- matching reasons
- conflict reasons

---

### `test_field_matcher.py`

Contains 45 matcher unit tests covering:

- camelCase normalization
- snake_case normalization
- kebab-case normalization
- PascalCase normalization
- acronym handling
- semantic concept detection
- email concepts
- phone concepts
- ID concepts
- date concepts
- name qualifier conflicts
- primary and secondary conflicts
- created and updated conflicts
- value-type detection
- email-format detection
- UUID-format detection
- date-time detection
- phone-format detection
- OpenAPI type compatibility
- OpenAPI format compatibility
- deterministic scoring
- score capping
- safe field mappings
- rejected field mappings

---

### `test_auto_healer.py`

Contains three integration tests.

The tests verify that:

- `userEmail -> email_address` generates a healed file
- `displayName -> email_address` is rejected
- `firstName -> last_name` is rejected

Temporary directories are used so the tests do not overwrite the real demo files.

---

## Requirements

- Python 3.10 or newer
- Flask
- PyYAML
- requests
- GitHub CLI, only for PR mode

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

For GitHub PR mode, install and authenticate GitHub CLI:

```bash
gh auth login
```

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/burak109/api-drift-healer-demo.git
cd api-drift-healer-demo
```

---

### 2. Create a virtual environment

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

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Start the mock API server

Open the first terminal:

```bash
python mock_server.py
```

The server runs at:

```text
http://localhost:3000
```

Keep this terminal open.

---

### 5. Run API Drift Healer

Open a second terminal:

```bash
python auto_healer.py
```

Expected output:

```text
=== API DRIFT HEALER V0.4 (SAFE SMART FIELD MATCHING) ===

[1] Running the original test case...
[*] Running test: Create User - Success (api_test_case.yaml)
[FAIL] Expected 201, got 400
       Error: missing required field: email_address

[!] Test FAILED! Triggering Healer...

[*] Healer: Starting drift analysis on 'api_test_case.yaml'...
[*] Evaluating candidate match: 'userEmail' -> 'email_address'
[+] Safe Drift Match Detected: 'userEmail' -> 'email_address'
    Score: 0.772 | Confidence: High
[+] Healed test file generated for demo: api_test_case.healed.yaml

[3] Automatically validating the healed test case...
[*] Running test: Create User - Success (api_test_case.healed.yaml)
[PASS] Expected 201, got 201

[PASS] Healed test validated successfully.
Golden Rule (No PASS, No PR) satisfied!

[4] Generating explainability report...
[+] Heal report generated: heal_report.md

[5] PR creation skipped. Local V0.4 report mode is active.
```

By default, the tool runs in local report mode and does not open a Pull Request.

---

## Local Report Mode

Run:

```bash
python auto_healer.py
```

Local report mode:

- runs the original failing test
- detects the contract drift
- evaluates the candidate field rename
- rejects unsafe mappings
- generates the healed test when safe
- reruns the healed test
- generates `heal_report.md`
- skips GitHub PR creation

This mode is useful for:

- local development
- debugging
- demonstrations
- reviewing the matcher decision
- validating safety changes

---

## GitHub PR Mode

PR creation is disabled by default.

To enable it, set:

```text
CREATE_PR=true
```

### macOS / Linux

```bash
CREATE_PR=true python auto_healer.py
```

### Windows PowerShell

```powershell
$env:CREATE_PR="true"
python auto_healer.py
```

Clear the PowerShell variable afterward:

```powershell
Remove-Item Env:CREATE_PR
```

PR mode requires:

- GitHub CLI installed
- GitHub CLI authenticated
- a Git repository
- a configured remote
- a clean working tree
- a safe matcher decision
- a locally passing healed test

If the working tree is not clean, the tool stops before creating a branch.

This prevents unrelated local changes from being mixed into the generated fix.

---

## Example Generated Report

After a successful safe heal, the tool generates:

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
The candidate field rename passed semantic, type, and format checks with a score of 0.772, above the 0.700 safety threshold.

## Smart Match Decision

- Match score: `0.772`
- Safety threshold: `0.700`
- Confidence: `High`
- Decision: `SAFE PATCH`

## Matching Evidence

- Normalized field tokens do not match exactly
- Shared semantic concept: email
- Value type 'string' matches OpenAPI type 'string'
- Detected value format 'email' matches OpenAPI format 'email'
- Normalized string similarity: 0.435

## Files
- Original test file: `api_test_case.yaml`
- Healed test file: `api_test_case.healed.yaml`
- OpenAPI contract: `openapi.yaml`

## Safety
This report was generated only after the healed test passed locally.

No PASS, No PR.
```

---

## Example Rejected Decision

Unsafe candidate:

```text
displayName -> email_address
```

Example decision:

```text
Score: 0.158
Threshold: 0.700
Confidence: Low
Decision: REJECT
```

Reasons include:

```text
No shared semantic concept was found
Detected value format conflicts with OpenAPI format 'email'
No strong matching anchor was found
Score is below the safety threshold
Hard safety conflict detected
```

No healed file is created for this candidate.

---

## Example Pull Request

When PR mode is enabled, the tool can open a reviewable Pull Request.

Example title:

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

The Pull Request includes:

- root cause
- applied fix
- validation result
- confidence
- match score
- safety threshold
- matching evidence
- generated report

The bot does not merge the Pull Request.

A human remains responsible for review and merge.

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

An automatic patch requires:

```text
1 missing required field
+
1 invalid existing field
+
a strong matching anchor
+
score meets the safety threshold
+
no semantic conflict
+
no qualifier conflict
+
no OpenAPI type conflict
+
no OpenAPI format conflict
+
healed test passes locally
```

A high score cannot override a hard safety conflict.

When the drift is complex, ambiguous, or risky, the tool stops.

That is intentional.

---

## Automated Tests

Run the complete V0.4 test suite:

```bash
python -m unittest -v \
  test_field_matcher.py \
  test_auto_healer.py
```

Current suite:

```text
45 matcher unit tests
+
3 healer integration tests
=
48 automated tests
```

The tests cover both successful healing and deliberate rejection.

Expected result:

```text
Ran 48 tests

OK
```

---

## Current Status

```text
V0     ✅ Core local heal proof
V0.1   ✅ One-command FAIL -> HEAL -> PASS flow
V0.2   ✅ Secure PR flow after local validation
V0.3   ✅ Explainability report generation
V0.3.1 ✅ CREATE_PR toggle and clean working tree guard
V0.4   ✅ Field-name normalization
V0.4   ✅ Semantic concept extraction
V0.4   ✅ Qualifier conflict guards
V0.4   ✅ OpenAPI type compatibility
V0.4   ✅ OpenAPI format compatibility
V0.4   ✅ Deterministic scoring
V0.4   ✅ Safety threshold
V0.4   ✅ SAFE PATCH and REJECT decisions
V0.4   ✅ Match evidence reporting
V0.4   ✅ 45 matcher unit tests
V0.4   ✅ 3 healer integration tests
```

---

## Roadmap

### V0.5 — CLI Arguments

Replace hardcoded file paths with command-line arguments.

Possible usage:

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
--threshold
```

---

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

---

### V1.1 — VS Code `.http` Adapter

Support REST Client and `.http` request files.

Example input:

```http
POST http://localhost:3000/users
Content-Type: application/json

{
  "name": "Test User",
  "userEmail": "qa_user@example.com"
}
```

Example healed request:

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

Initial goals:

- locate simple request payload dictionaries
- associate payloads with request URLs and methods
- generate suggested patches
- preserve surrounding test logic
- reject risky automatic rewrites

---

### V2 — GitHub Actions Integration

Run API Drift Healer inside CI.

Possible flow:

```text
CI test fails
        ↓
API Drift Healer reads OpenAPI
        ↓
Candidate patch evaluated
        ↓
Healed test passes
        ↓
Bot opens a PR or comments on an existing PR
```

---

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
- API keys for local report mode

This makes the early prototype easier to inspect, test, and trust.

GitHub authentication is only needed when PR mode is enabled.

---

## Demo Summary

```text
OpenAPI requires:
email_address

Test sends:
userEmail

Original test:
400 FAIL

Smart matcher evaluates:
- normalized field names
- semantic concepts
- qualifiers
- OpenAPI type
- OpenAPI format
- normalized string similarity
- deterministic score
- hard safety conflicts

Decision:
SAFE PATCH

Match score:
0.772

Safety threshold:
0.700

Healer applies:
userEmail -> email_address

Healed test:
201 PASS

Report:
Generated with score and matching evidence

PR:
Optional and human-reviewable
```

---

## License

MIT
