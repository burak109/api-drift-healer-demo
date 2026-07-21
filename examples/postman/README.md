# Postman Collection Example

This example shows how API Drift Healer repairs a simple field rename inside a Postman Collection v2.1 file.

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

## Files

```text
examples/postman/
├── create-user.postman_collection.json
├── openapi.yaml
└── README.md
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

Expected decision:

```text
Decision: SAFE_PATCH
Candidate: userEmail -> email_address
Score: 0.772
Threshold: 0.700
Confidence: High
```

Dry-run displays the diff but does not create a file.

## Generate a Healed Collection

```bash
api-drift-healer postman heal \
  --collection examples/postman/create-user.postman_collection.json \
  --request "Create User" \
  --openapi examples/postman/openapi.yaml \
  --output create-user.healed.postman_collection.json
```

The original collection is preserved.

## Run the Complete Demo

```bash
./scripts/demo_postman.sh
```

The script performs the dry-run, writes a temporary healed collection, validates its JSON, compares the old and new request bodies, and removes the temporary output.

## Current Scope

Supported:

- Postman Collection v2.1
- nested folders
- exact request names
- raw JSON object bodies
- one top-level field rename
- exact OpenAPI path and method matching

Not yet supported:

- form-data
- URL-encoded bodies
- GraphQL
- nested repairs
- multiple repairs
- referenced or composed OpenAPI schemas
- Newman runtime validation
