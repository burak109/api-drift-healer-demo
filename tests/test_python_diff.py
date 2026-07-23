import json
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from api_drift_healer.python_diff import (
    PythonDiffError,
    build_python_patch_suggestion,
)
from api_drift_healer.python_request_analyzer import (
    analyze_python_request_file,
)


class PythonDiffTests(unittest.TestCase):
    def test_generates_safe_diff_without_changing_source(self) -> None:
        python_source = dedent(
            '''
            import requests

            payload = {
                "name": "Test User",
                "userEmail": "qa_user@example.com",
            }

            response = requests.post(
                "http://localhost:3000/users",
                json=payload,
            )

            assert response.status_code == 201
            '''
        ).lstrip()

        with tempfile.TemporaryDirectory() as temp_directory:
            python_path, openapi_path = self._write_files(
                temp_directory=temp_directory,
                python_source=python_source,
            )

            analysis_result = analyze_python_request_file(
                python_path=python_path,
                openapi_path=openapi_path,
            )

            suggestion = build_python_patch_suggestion(
                analysis_result
            )

            self.assertEqual(
                suggestion.old_field,
                "userEmail",
            )
            self.assertEqual(
                suggestion.new_field,
                "email_address",
            )

            self.assertIn(
                '-    "userEmail": "qa_user@example.com",',
                suggestion.unified_diff,
            )
            self.assertIn(
                '+    "email_address": "qa_user@example.com",',
                suggestion.unified_diff,
            )

            self.assertIn(
                '"email_address": "qa_user@example.com"',
                suggestion.suggested_source,
            )

            self.assertEqual(
                python_path.read_text(encoding="utf-8"),
                python_source,
            )

    def test_does_not_replace_same_text_used_as_value(self) -> None:
        python_source = dedent(
            '''
            import requests

            payload = {
                "name": "userEmail",
                "userEmail": "qa_user@example.com",
            }

            requests.post(
                "http://localhost:3000/users",
                json=payload,
            )
            '''
        ).lstrip()

        with tempfile.TemporaryDirectory() as temp_directory:
            python_path, openapi_path = self._write_files(
                temp_directory=temp_directory,
                python_source=python_source,
            )

            analysis_result = analyze_python_request_file(
                python_path=python_path,
                openapi_path=openapi_path,
            )

            suggestion = build_python_patch_suggestion(
                analysis_result
            )

            self.assertIn(
                '"name": "userEmail"',
                suggestion.suggested_source,
            )
            self.assertIn(
                '"email_address": "qa_user@example.com"',
                suggestion.suggested_source,
            )

    def test_preserves_single_quote_style(self) -> None:
        python_source = dedent(
            """
            import requests

            payload = {
                'name': 'Test User',
                'userEmail': 'qa_user@example.com',
            }

            requests.post(
                'http://localhost:3000/users',
                json=payload,
            )
            """
        ).lstrip()

        with tempfile.TemporaryDirectory() as temp_directory:
            python_path, openapi_path = self._write_files(
                temp_directory=temp_directory,
                python_source=python_source,
            )

            analysis_result = analyze_python_request_file(
                python_path=python_path,
                openapi_path=openapi_path,
            )

            suggestion = build_python_patch_suggestion(
                analysis_result
            )

            self.assertIn(
                "'email_address': 'qa_user@example.com'",
                suggestion.suggested_source,
            )

    def test_rejects_unsafe_analysis(self) -> None:
        python_source = dedent(
            '''
            import requests

            payload = {
                "name": "Test User",
                "displayName": "Burak",
            }

            requests.post(
                "http://localhost:3000/users",
                json=payload,
            )
            '''
        ).lstrip()

        with tempfile.TemporaryDirectory() as temp_directory:
            python_path, openapi_path = self._write_files(
                temp_directory=temp_directory,
                python_source=python_source,
            )

            analysis_result = analyze_python_request_file(
                python_path=python_path,
                openapi_path=openapi_path,
            )

            self.assertFalse(
                analysis_result.analysis.safe_to_patch
            )

            with self.assertRaisesRegex(
                PythonDiffError,
                "SAFE_PATCH",
            ):
                build_python_patch_suggestion(
                    analysis_result
                )

    @staticmethod
    def _write_files(
        temp_directory: str,
        python_source: str,
    ) -> tuple[Path, Path]:
        temp_path = Path(temp_directory)

        python_path = temp_path / "test_create_user.py"
        openapi_path = temp_path / "openapi.json"

        openapi_document = {
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
                                            "name",
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

        python_path.write_text(
            python_source,
            encoding="utf-8",
        )
        openapi_path.write_text(
            json.dumps(openapi_document),
            encoding="utf-8",
        )

        return python_path, openapi_path


if __name__ == "__main__":
    unittest.main()