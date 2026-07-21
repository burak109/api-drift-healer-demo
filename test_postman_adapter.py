import json
import tempfile
import unittest
from pathlib import Path

from api_drift_healer.adapters.postman import (
    PostmanAdapterError,
    load_postman_collection,
    normalize_postman_request,
    normalize_postman_request_file,
)


POSTMAN_SCHEMA = (
    "https://schema.getpostman.com/"
    "json/collection/v2.1.0/collection.json"
)


def make_request_item(
    *,
    name: str = "Create User",
    method: str = "POST",
    url: object | None = None,
    raw_body: str | None = None,
    body_mode: str = "raw",
) -> dict[str, object]:
    if url is None:
        url = {
            "raw": "{{baseUrl}}/users",
            "path": ["users"],
        }

    if raw_body is None:
        raw_body = json.dumps(
            {
                "name": "Test User",
                "userEmail": "qa_user@example.com",
            }
        )

    return {
        "name": name,
        "request": {
            "method": method,
            "url": url,
            "body": {
                "mode": body_mode,
                "raw": raw_body,
            },
        },
    }


def make_collection(
    items: list[object],
    *,
    schema: str = POSTMAN_SCHEMA,
) -> dict[str, object]:
    return {
        "info": {
            "name": "API Drift Healer Demo",
            "schema": schema,
        },
        "item": items,
    }


class PostmanAdapterTests(unittest.TestCase):
    def test_normalizes_nested_postman_request(self) -> None:
        collection = make_collection(
            [
                {
                    "name": "Users",
                    "item": [
                        make_request_item(method="post"),
                    ],
                }
            ]
        )

        request = normalize_postman_request(
            collection=collection,
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

    def test_extracts_path_from_raw_absolute_url(self) -> None:
        collection = make_collection(
            [
                make_request_item(
                    url="https://api.example.com/users?source=postman"
                )
            ]
        )

        request = normalize_postman_request(
            collection=collection,
            request_name="Create User",
        )

        self.assertEqual(request.path, "/users")

    def test_extracts_path_from_variable_raw_url(self) -> None:
        collection = make_collection(
            [
                make_request_item(
                    url="{{baseUrl}}/users"
                )
            ]
        )

        request = normalize_postman_request(
            collection=collection,
            request_name="Create User",
        )

        self.assertEqual(request.path, "/users")

    def test_supports_postman_path_value_objects(self) -> None:
        collection = make_collection(
            [
                make_request_item(
                    url={
                        "raw": "{{baseUrl}}/users/create",
                        "path": [
                            {"type": "text", "value": "users"},
                            {"type": "text", "value": "create"},
                        ],
                    }
                )
            ]
        )

        request = normalize_postman_request(
            collection=collection,
            request_name="Create User",
        )

        self.assertEqual(request.path, "/users/create")

    def test_rejects_missing_request_name(self) -> None:
        collection = make_collection(
            [make_request_item()]
        )

        with self.assertRaisesRegex(
            PostmanAdapterError,
            "not found",
        ):
            normalize_postman_request(
                collection=collection,
                request_name="Delete User",
            )

    def test_rejects_duplicate_request_names(self) -> None:
        collection = make_collection(
            [
                make_request_item(),
                make_request_item(),
            ]
        )

        with self.assertRaisesRegex(
            PostmanAdapterError,
            "Multiple",
        ):
            normalize_postman_request(
                collection=collection,
                request_name="Create User",
            )

    def test_rejects_unsupported_body_mode(self) -> None:
        collection = make_collection(
            [
                make_request_item(
                    body_mode="formdata"
                )
            ]
        )

        with self.assertRaisesRegex(
            PostmanAdapterError,
            "raw JSON",
        ):
            normalize_postman_request(
                collection=collection,
                request_name="Create User",
            )

    def test_rejects_invalid_raw_json(self) -> None:
        collection = make_collection(
            [
                make_request_item(
                    raw_body="{invalid-json"
                )
            ]
        )

        with self.assertRaisesRegex(
            PostmanAdapterError,
            "not valid JSON",
        ):
            normalize_postman_request(
                collection=collection,
                request_name="Create User",
            )

    def test_rejects_json_array_body(self) -> None:
        collection = make_collection(
            [
                make_request_item(
                    raw_body='["userEmail"]'
                )
            ]
        )

        with self.assertRaisesRegex(
            PostmanAdapterError,
            "JSON object",
        ):
            normalize_postman_request(
                collection=collection,
                request_name="Create User",
            )

    def test_rejects_unsupported_collection_version(self) -> None:
        collection = make_collection(
            [make_request_item()],
            schema=(
                "https://schema.getpostman.com/"
                "json/collection/v2.0.0/collection.json"
            ),
        )

        with self.assertRaisesRegex(
            PostmanAdapterError,
            "v2.1",
        ):
            normalize_postman_request(
                collection=collection,
                request_name="Create User",
            )

    def test_loads_and_normalizes_collection_file(self) -> None:
        collection = make_collection(
            [make_request_item()]
        )

        with tempfile.TemporaryDirectory() as temp_directory:
            collection_path = (
                Path(temp_directory)
                / "demo.postman_collection.json"
            )

            collection_path.write_text(
                json.dumps(collection),
                encoding="utf-8",
            )

            loaded_collection = load_postman_collection(
                collection_path
            )

            request = normalize_postman_request_file(
                collection_path=collection_path,
                request_name="Create User",
            )

        self.assertEqual(
            loaded_collection["info"]["name"],
            "API Drift Healer Demo",
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/users")


if __name__ == "__main__":
    unittest.main()
