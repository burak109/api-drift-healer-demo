# Pytest / Requests Adapter Example

This example shows how API Drift Healer detects a stale request field in a Python API test.

The Python test sends:

```python
payload = {
    "name": "Test User",
    "userEmail": "qa_user@example.com",
}
```

The OpenAPI contract requires:

```text
email_address
```

Run the analysis from the repository root:

```bash
api-drift-healer pytest analyze \
  --file examples/pytest_requests/test_create_user.py \
  --openapi examples/pytest_requests/openapi.yaml
```

Expected decision:

```text
Request       : POST /users
Decision      : SAFE_PATCH
Old field     : userEmail
Required field: email_address
Score         : 0.772
Confidence    : High
```

Expected suggestion:

```diff
-        "userEmail": "qa_user@example.com",
+        "email_address": "qa_user@example.com",
```

The adapter is suggestion-only.

```text
Detect. Suggest. Never overwrite.
```

The original Python file is not imported, executed, or modified.

## Supported in V1.3

- one Python file
- one `requests.post`, `requests.put`, or `requests.patch` call
- literal URL strings
- literal JSON-compatible dictionaries
- named or inline `json=` payloads
- one top-level field rename
- deterministic OpenAPI drift analysis
- unified diff output

## Not Supported Yet

- automatic Python rewrites
- multiple request calls in one file
- dynamic or f-string URLs
- fixture or helper-generated payloads
- dynamic values inside payload dictionaries
- `requests.Session`
- `httpx` or async clients
- nested or multiple field repairs
