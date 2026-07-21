# Postman Collection Example

This example represents the first Postman adapter scenario for API Drift Healer.

## Scenario

The Postman request named `Create User` sends:

```json
{
  "name": "Test User",
  "userEmail": "qa_user@example.com"
}
```

The OpenAPI contract for `POST /users` requires:

```text
email_address
```

The expected safe field repair is:

```text
userEmail -> email_address
```

## Files

```text
examples/postman/
├── create-user.postman_collection.json
├── openapi.yaml
└── README.md
```

## Inspect the Normalized Request

Run from the repository root:

```bash
python - <<'PY'
from api_drift_healer.adapters.postman import (
    normalize_postman_request_file,
)

request = normalize_postman_request_file(
    collection_path=(
        "examples/postman/"
        "create-user.postman_collection.json"
    ),
    request_name="Create User",
)

print(f"Name:   {request.name}")
print(f"Method: {request.method}")
print(f"Path:   {request.path}")
print(f"Body:   {request.body}")
PY
```

Expected result:

```text
Name:   Create User
Method: POST
Path:   /users
Body:   {'name': 'Test User', 'userEmail': 'qa_user@example.com'}
```

At this stage, the Postman adapter reads and normalizes the request.

Collection patching and validation will be connected in the next V1 steps.
