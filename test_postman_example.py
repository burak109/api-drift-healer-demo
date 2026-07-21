import unittest
from pathlib import Path

import yaml

from api_drift_healer.adapters.postman import (
    normalize_postman_request_file,
)


PROJECT_ROOT = Path(__file__).resolve().parent
EXAMPLE_DIRECTORY = PROJECT_ROOT / "examples" / "postman"
COLLECTION_PATH = (
    EXAMPLE_DIRECTORY
    / "create-user.postman_collection.json"
)
OPENAPI_PATH = EXAMPLE_DIRECTORY / "openapi.yaml"


class PostmanExampleIntegrationTests(unittest.TestCase):
    def test_example_collection_normalizes_expected_request(self) -> None:
        request = normalize_postman_request_file(
            collection_path=COLLECTION_PATH,
            request_name="Create User",
        )

        self.assertEqual(request.name, "Create User")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/users")
        self.assertEqual(
            request.body,
            {
                "name": "Test User",
                "userEmail": "qa_user@example.com",
            },
        )

    def test_example_openapi_requires_new_email_field(self) -> None:
        with OPENAPI_PATH.open(encoding="utf-8") as openapi_file:
            openapi = yaml.safe_load(openapi_file)

        request_schema = openapi[
            "paths"
        ][
            "/users"
        ][
            "post"
        ][
            "requestBody"
        ][
            "content"
        ][
            "application/json"
        ][
            "schema"
        ]

        self.assertIn(
            "email_address",
            request_schema["required"],
        )
        self.assertIn(
            "email_address",
            request_schema["properties"],
        )
        self.assertNotIn(
            "userEmail",
            request_schema["properties"],
        )


if __name__ == "__main__":
    unittest.main()
