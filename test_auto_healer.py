import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

import auto_healer


class SmartFieldMatchingIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = TemporaryDirectory()
        self.temp_path = Path(self.temp_directory.name)

        self.original_test_case_file = auto_healer.TEST_CASE_FILE
        self.original_healed_test_file = auto_healer.HEALED_TEST_FILE
        self.original_openapi_file = auto_healer.OPENAPI_FILE

        auto_healer.TEST_CASE_FILE = str(
            self.temp_path / "api_test_case.yaml"
        )
        auto_healer.HEALED_TEST_FILE = str(
            self.temp_path / "api_test_case.healed.yaml"
        )
        auto_healer.OPENAPI_FILE = str(
            self.temp_path / "openapi.yaml"
        )

    def tearDown(self) -> None:
        auto_healer.TEST_CASE_FILE = self.original_test_case_file
        auto_healer.HEALED_TEST_FILE = self.original_healed_test_file
        auto_healer.OPENAPI_FILE = self.original_openapi_file

        self.temp_directory.cleanup()

    @staticmethod
    def write_yaml(path: str, data: dict) -> None:
        Path(path).write_text(
            yaml.safe_dump(
                data,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def write_openapi(
        self,
        required_field: str,
        target_schema: dict,
        additional_properties: dict | None = None,
    ) -> None:
        properties = dict(additional_properties or {})
        properties[required_field] = target_schema

        openapi_data = {
            "paths": {
                "/users": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": [required_field],
                                        "properties": properties,
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        self.write_yaml(
            auto_healer.OPENAPI_FILE,
            openapi_data,
        )

    def write_test_case(self, body: dict) -> None:
        self.write_yaml(
            auto_healer.TEST_CASE_FILE,
            {
                "name": "Smart Field Matching Test",
                "method": "POST",
                "url": "http://localhost:3000/users",
                "expected_status": 201,
                "body": body,
            },
        )

    def test_safe_email_match_generates_healed_file(self) -> None:
        self.write_openapi(
            required_field="email_address",
            target_schema={
                "type": "string",
                "format": "email",
            },
            additional_properties={
                "name": {
                    "type": "string",
                }
            },
        )

        self.write_test_case(
            {
                "name": "Test User",
                "userEmail": "qa_user@example.com",
            }
        )

        result = auto_healer.deterministic_heal()

        self.assertIsNotNone(result)
        self.assertEqual(result["old_field"], "userEmail")
        self.assertEqual(result["new_field"], "email_address")
        self.assertTrue(
            Path(auto_healer.HEALED_TEST_FILE).exists()
        )

        healed_data = yaml.safe_load(
            Path(auto_healer.HEALED_TEST_FILE).read_text(
                encoding="utf-8"
            )
        )

        self.assertNotIn(
            "userEmail",
            healed_data["body"],
        )
        self.assertEqual(
            healed_data["body"]["email_address"],
            "qa_user@example.com",
        )
        self.assertGreaterEqual(
            result["match_score"],
            result["match_threshold"],
        )

    def test_unsafe_name_to_email_match_is_rejected(self) -> None:
        self.write_openapi(
            required_field="email_address",
            target_schema={
                "type": "string",
                "format": "email",
            },
            additional_properties={
                "name": {
                    "type": "string",
                }
            },
        )

        self.write_test_case(
            {
                "name": "Test User",
                "displayName": "Test User",
            }
        )

        result = auto_healer.deterministic_heal()

        self.assertIsNone(result)
        self.assertFalse(
            Path(auto_healer.HEALED_TEST_FILE).exists()
        )

    def test_first_name_to_last_name_is_rejected(self) -> None:
        self.write_openapi(
            required_field="last_name",
            target_schema={
                "type": "string",
            },
        )

        self.write_test_case(
            {
                "firstName": "Burak",
            }
        )

        result = auto_healer.deterministic_heal()

        self.assertIsNone(result)
        self.assertFalse(
            Path(auto_healer.HEALED_TEST_FILE).exists()
        )


if __name__ == "__main__":
    unittest.main()
