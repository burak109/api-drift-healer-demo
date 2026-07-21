import json
import unittest

from api_drift_healer.adapters.postman import (
    PostmanAdapterError,
    normalize_postman_request,
    patch_postman_request_body,
)


POSTMAN_SCHEMA = (
    "https://schema.getpostman.com/"
    "json/collection/v2.1.0/collection.json"
)


def make_collection(
    body: dict | None = None,
) -> dict:
    request_body = body or {
        "name": "Test User",
        "userEmail": "qa_user@example.com",
    }

    return {
        "info": {
            "name": "Patcher Test",
            "schema": POSTMAN_SCHEMA,
        },
        "item": [
            {
                "name": "Users",
                "item": [
                    {
                        "name": "Create User",
                        "request": {
                            "method": "POST",
                            "url": {
                                "raw": "{{baseUrl}}/users",
                                "path": ["users"],
                            },
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps(
                                    request_body,
                                    indent=2,
                                ),
                            },
                        },
                    }
                ],
            }
        ],
    }


class PostmanPatcherTests(unittest.TestCase):
    def test_renames_body_field(self) -> None:
        collection = make_collection()

        patched = patch_postman_request_body(
            collection=collection,
            request_name="Create User",
            old_field="userEmail",
            new_field="email_address",
        )

        request = normalize_postman_request(
            collection=patched,
            request_name="Create User",
        )

        self.assertEqual(
            request.body,
            {
                "name": "Test User",
                "email_address": "qa_user@example.com",
            },
        )

    def test_does_not_mutate_original_collection(self) -> None:
        collection = make_collection()

        patch_postman_request_body(
            collection=collection,
            request_name="Create User",
            old_field="userEmail",
            new_field="email_address",
        )

        original_request = normalize_postman_request(
            collection=collection,
            request_name="Create User",
        )

        self.assertIn("userEmail", original_request.body)
        self.assertNotIn(
            "email_address",
            original_request.body,
        )

    def test_preserves_field_position(self) -> None:
        collection = make_collection()

        patched = patch_postman_request_body(
            collection=collection,
            request_name="Create User",
            old_field="userEmail",
            new_field="email_address",
        )

        request = normalize_postman_request(
            collection=patched,
            request_name="Create User",
        )

        self.assertEqual(
            list(request.body),
            ["name", "email_address"],
        )

    def test_rejects_missing_old_field(self) -> None:
        collection = make_collection()

        with self.assertRaisesRegex(
            PostmanAdapterError,
            "was not found",
        ):
            patch_postman_request_body(
                collection=collection,
                request_name="Create User",
                old_field="phoneNumber",
                new_field="phone_number",
            )

    def test_rejects_overwriting_existing_field(self) -> None:
        collection = make_collection(
            {
                "userEmail": "qa_user@example.com",
                "email_address": "existing@example.com",
            }
        )

        with self.assertRaisesRegex(
            PostmanAdapterError,
            "already exists",
        ):
            patch_postman_request_body(
                collection=collection,
                request_name="Create User",
                old_field="userEmail",
                new_field="email_address",
            )


if __name__ == "__main__":
    unittest.main()
