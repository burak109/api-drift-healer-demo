# Basic YAML Example

This example shows how API Drift Healer detects and repairs a simple field rename caused by OpenAPI contract drift.

## Scenario

The OpenAPI contract requires:

```yaml
email_address
```

But the API test still sends:

```yaml
userEmail
```

API Drift Healer detects the mismatch and proposes:

```text
userEmail -> email_address
```

The healed test is validated locally before it is accepted.

## 1. Install the CLI

Run this command from the repository root:

```bash
python -m pip install -e .
```

## 2. Start the Mock API

Open a terminal in the repository root:

```bash
python mock_server.py
```

Keep the mock server running.

## 3. Preview the Repair

Open another terminal in the repository root:

```bash
api-drift-healer heal \
  --test examples/basic_yaml/api_test_case.yaml \
  --openapi examples/basic_yaml/openapi.yaml \
  --dry-run
```

Dry-run mode analyzes the drift without changing or creating test files.

## 4. Generate and Validate the Healed Test

```bash
api-drift-healer heal \
  --test examples/basic_yaml/api_test_case.yaml \
  --openapi examples/basic_yaml/openapi.yaml \
  --output examples/basic_yaml/api_test_case.healed.yaml
```

Expected workflow:

```text
Original request: 400 FAIL
Detected drift: userEmail -> email_address
Healed request: 201 PASS
```

## Safety Rule

API Drift Healer accepts the generated patch only after the healed test passes locally.

```text
No PASS, no accepted patch.
```
