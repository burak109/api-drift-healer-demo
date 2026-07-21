import tempfile
import unittest
from pathlib import Path

import yaml

from api_drift_healer.openapi_resolver import (
    OpenApiResolverError,
    load_openapi_document,
    resolve_request_schema,
    resolve_request_schema_file,
)


def make_openapi_schema() -> dict:
    return {
        "openapi": "3.0.0",
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": [
                                        "email_address",
                                    ],
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                        },
                                        "email_address": {
                                            "type": "string",
                                            "format": "email",
                                        },
                                    },
                                }
                            }
                        }
                    }
                }
            }
        },
    }


class OpenApiResolverTests(unittest.TestCase):
    def test_resolves_exact_request_schema(self) -> None:
        result = resolve_request_schema(
            document=make_openapi_schema(),
            method="POST",
            path="/users",
        )

        self.assertEqual(result.method, "POST")
        self.assertEqual(result.path, "/users")
        self.assertEqual(
            result.required_fields,
            ("email_address",),
        )
        self.assertEqual(
            result.properties["email_address"],
            {
                "type": "string",
                "format": "email",
            },
        )

    def test_normalizes_method_and_path(self) -> None:
        result = resolve_request_schema(
            document=make_openapi_schema(),
            method=" post ",
            path="users",
        )

        self.assertEqual(result.method, "POST")
        self.assertEqual(result.path, "/users")

    def test_loads_and_resolves_openapi_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            openapi_path = (
                Path(temp_directory)
                / "openapi.yaml"
            )

            openapi_path.write_text(
                yaml.safe_dump(
                    make_openapi_schema(),
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            loaded = load_openapi_document(openapi_path)

            result = resolve_request_schema_file(
                openapi_path=openapi_path,
                method="POST",
                path="/users",
            )

        self.assertIn("paths", loaded)
        self.assertEqual(
            result.required_fields,
            ("email_address",),
        )

    def test_rejects_invalid_yaml_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            openapi_path = (
                Path(temp_directory)
                / "openapi.yaml"
            )

            openapi_path.write_text(
                "paths: [invalid",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                OpenApiResolverError,
                "not valid YAML",
            ):
                load_openapi_document(openapi_path)

    def test_rejects_missing_paths_object(self) -> None:
        with self.assertRaisesRegex(
            OpenApiResolverError,
            "paths",
        ):
            resolve_request_schema(
                document={"openapi": "3.0.0"},
                method="POST",
                path="/users",
            )

    def test_rejects_unknown_path(self) -> None:
        with self.assertRaisesRegex(
            OpenApiResolverError,
            "path not found",
        ):
            resolve_request_schema(
                document=make_openapi_schema(),
                method="POST",
                path="/orders",
            )

    def test_rejects_unknown_method(self) -> None:
        with self.assertRaisesRegex(
            OpenApiResolverError,
            "operation not found",
        ):
            resolve_request_schema(
                document=make_openapi_schema(),
                method="DELETE",
                path="/users",
            )

    def test_rejects_missing_request_body(self) -> None:
        document = make_openapi_schema()

        document["paths"]["/users"]["post"].pop(
            "requestBody"
        )

        with self.assertRaisesRegex(
            OpenApiResolverError,
            "no request body",
        ):
            resolve_request_schema(
                document=document,
                method="POST",
                path="/users",
            )

    def test_rejects_missing_application_json(self) -> None:
        document = make_openapi_schema()

        document[
            "paths"
        ][
            "/users"
        ][
            "post"
        ][
            "requestBody"
        ][
            "content"
        ] = {
            "text/plain": {
                "schema": {
                    "type": "string",
                }
            }
        }

        with self.assertRaisesRegex(
            OpenApiResolverError,
            "application/json",
        ):
            resolve_request_schema(
                document=document,
                method="POST",
                path="/users",
            )

    def test_rejects_referenced_schema(self) -> None:
        document = make_openapi_schema()

        document[
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
        ] = {
            "$ref": "#/components/schemas/User"
        }

        with self.assertRaisesRegex(
            OpenApiResolverError,
            "Referenced",
        ):
            resolve_request_schema(
                document=document,
                method="POST",
                path="/users",
            )

    def test_rejects_non_object_schema(self) -> None:
        document = make_openapi_schema()

        schema = document[
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

        schema["type"] = "array"

        with self.assertRaisesRegex(
            OpenApiResolverError,
            "must describe an object",
        ):
            resolve_request_schema(
                document=document,
                method="POST",
                path="/users",
            )

    def test_rejects_invalid_required_value(self) -> None:
        document = make_openapi_schema()

        schema = document[
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

        schema["required"] = "email_address"

        with self.assertRaisesRegex(
            OpenApiResolverError,
            "required.*list",
        ):
            resolve_request_schema(
                document=document,
                method="POST",
                path="/users",
            )

    def test_rejects_required_field_without_property(self) -> None:
        document = make_openapi_schema()

        schema = document[
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

        schema["properties"].pop("email_address")

        with self.assertRaisesRegex(
            OpenApiResolverError,
            "missing from properties",
        ):
            resolve_request_schema(
                document=document,
                method="POST",
                path="/users",
            )


if __name__ == "__main__":
    unittest.main()
