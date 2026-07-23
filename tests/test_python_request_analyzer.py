import json
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from api_drift_healer.python_request_analyzer import (
    PythonRequestAnalysisError,
    analyze_python_request_file,
    extract_request_path,
)


class PythonRequestAnalyzerTests(unittest.TestCase):
    def test_extracts_path_from_full_url_with_query(self) -> None:
        path = extract_request_path(
            "http://localhost:3000/users?active=true#result"
        )

        self.assertEqual(path, "/users")

    def test_analyzes_safe_patch_without_changing_source(self) -> None:
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

        with tempfile.TemporaryDirectory() as temp_directory:
            temp_path = Path(temp_directory)

            python_path = temp_path / "test_create_user.py"
            openapi_path = temp_path / "openapi.json"

            python_path.write_text(
                python_source,
                encoding="utf-8",
            )
            openapi_path.write_text(
                json.dumps(openapi_document),
                encoding="utf-8",
            )

            result = analyze_python_request_file(
                python_path=python_path,
                openapi_path=openapi_path,
            )

            self.assertEqual(
                result.normalized_request.method,
                "POST",
            )
            self.assertEqual(
                result.normalized_request.path,
                "/users",
            )
            self.assertEqual(
                result.normalized_request.body,
                {
                    "name": "Test User",
                    "userEmail": "qa_user@example.com",
                },
            )

            self.assertEqual(
                result.analysis.decision,
                "SAFE_PATCH",
            )
            self.assertEqual(
                result.analysis.old_field,
                "userEmail",
            )
            self.assertEqual(
                result.analysis.new_field,
                "email_address",
            )

            self.assertEqual(
                python_path.read_text(encoding="utf-8"),
                python_source,
            )

    def test_rejects_file_without_supported_request(self) -> None:
        python_source = dedent(
            '''
            import requests

            response = requests.get(
                "http://localhost:3000/users"
            )
            '''
        ).lstrip()

        with tempfile.TemporaryDirectory() as temp_directory:
            python_path = (
                Path(temp_directory) / "test_list_users.py"
            )

            python_path.write_text(
                python_source,
                encoding="utf-8",
            )

            with self.assertRaises(
                PythonRequestAnalysisError
            ):
                analyze_python_request_file(
                    python_path=python_path,
                    openapi_path="unused-openapi.yaml",
                )

    def test_rejects_multiple_supported_requests(self) -> None:
        python_source = dedent(
            '''
            import requests

            payload = {
                "userEmail": "qa_user@example.com",
            }

            requests.post(
                "http://localhost:3000/users",
                json=payload,
            )

            requests.patch(
                "http://localhost:3000/users/1",
                json=payload,
            )
            '''
        ).lstrip()

        with tempfile.TemporaryDirectory() as temp_directory:
            python_path = (
                Path(temp_directory) / "test_users.py"
            )

            python_path.write_text(
                python_source,
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                PythonRequestAnalysisError,
                "exactly one request",
            ):
                analyze_python_request_file(
                    python_path=python_path,
                    openapi_path="unused-openapi.yaml",
                )


if __name__ == "__main__":
    unittest.main()