import json
import tempfile
import unittest
from pathlib import Path

from api_drift_healer.python_batch_analyzer import (
    analyze_python_test_directory,
)


def build_openapi_document() -> dict:
    request_schema = {
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

    return {
        "openapi": "3.0.0",
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": request_schema,
                            }
                        }
                    }
                }
            },
            "/profiles": {
                "put": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": request_schema,
                            }
                        }
                    }
                }
            },
        },
    }


class PythonBatchAnalyzerTests(unittest.TestCase):
    def _write_file(
        self,
        root: Path,
        relative_path: str,
        content: str,
    ) -> Path:
        file_path = root / relative_path
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        file_path.write_text(
            content,
            encoding="utf-8",
        )
        return file_path

    def _write_openapi(
        self,
        root: Path,
    ) -> Path:
        openapi_path = root / "openapi.json"
        openapi_path.write_text(
            json.dumps(build_openapi_document()),
            encoding="utf-8",
        )
        return openapi_path

    def test_analyzes_multiple_files_endpoints_and_methods(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            tests_directory = root / "tests"
            openapi_path = self._write_openapi(root)

            self._write_file(
                tests_directory,
                "test_create_user.py",
                '''
import requests


def test_create_user():
    requests.post(
        "http://localhost:3000/users",
        json={
            "name": "Create User",
            "userEmail": "create@example.com",
        },
    )
''',
            )

            self._write_file(
                tests_directory,
                "profiles/profile_test.py",
                '''
import requests


def test_update_profile():
    requests.put(
        "http://localhost:3000/profiles",
        json={
            "name": "Profile User",
            "userEmail": "profile@example.com",
        },
    )
''',
            )

            result = analyze_python_test_directory(
                directory=tests_directory,
                openapi_path=openapi_path,
            )

            self.assertEqual(result.files_scanned, 2)
            self.assertEqual(result.requests_discovered, 2)
            self.assertEqual(result.requests_analyzed, 2)
            self.assertEqual(len(result.results), 2)
            self.assertEqual(result.scan_errors, ())
            self.assertEqual(result.analysis_errors, ())

            self.assertEqual(
                tuple(
                    item.normalized_request.method
                    for item in result.results
                ),
                (
                    "PUT",
                    "POST",
                ),
            )

            self.assertEqual(
                tuple(
                    item.normalized_request.path
                    for item in result.results
                ),
                (
                    "/profiles",
                    "/users",
                ),
            )

            self.assertEqual(
                tuple(
                    item.analysis.decision
                    for item in result.results
                ),
                (
                    "SAFE_PATCH",
                    "SAFE_PATCH",
                ),
            )

            self.assertEqual(
                tuple(
                    item.request.test_name
                    for item in result.results
                ),
                (
                    "test_update_profile",
                    "test_create_user",
                ),
            )

    def test_continues_when_one_endpoint_cannot_be_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            tests_directory = root / "tests"
            openapi_path = self._write_openapi(root)

            self._write_file(
                tests_directory,
                "test_create_user.py",
                '''
import requests


def test_create_user():
    requests.post(
        "http://localhost:3000/users",
        json={
            "name": "Valid User",
            "userEmail": "valid@example.com",
        },
    )
''',
            )

            self._write_file(
                tests_directory,
                "test_missing_endpoint.py",
                '''
import requests


def test_missing_endpoint():
    requests.patch(
        "http://localhost:3000/missing",
        json={
            "name": "Missing User",
            "userEmail": "missing@example.com",
        },
    )
''',
            )

            result = analyze_python_test_directory(
                directory=tests_directory,
                openapi_path=openapi_path,
            )

            self.assertEqual(result.files_scanned, 2)
            self.assertEqual(result.requests_discovered, 2)
            self.assertEqual(result.requests_analyzed, 1)
            self.assertEqual(len(result.results), 1)
            self.assertEqual(len(result.analysis_errors), 1)

            error = result.analysis_errors[0]

            self.assertEqual(
                error.file_path.relative_to(tests_directory),
                Path("test_missing_endpoint.py"),
            )
            self.assertEqual(
                error.request.test_name,
                "test_missing_endpoint",
            )
            self.assertEqual(
                error.request.method,
                "PATCH",
            )
            self.assertEqual(
                error.request.url,
                "http://localhost:3000/missing",
            )
            self.assertTrue(error.message)

    def test_preserves_scan_errors_and_analyzes_valid_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            tests_directory = root / "tests"
            openapi_path = self._write_openapi(root)

            self._write_file(
                tests_directory,
                "test_valid.py",
                '''
import requests


def test_valid():
    requests.post(
        "http://localhost:3000/users",
        json={
            "name": "Valid User",
            "userEmail": "valid@example.com",
        },
    )
''',
            )

            self._write_file(
                tests_directory,
                "test_invalid.py",
                '''
def test_invalid(
''',
            )

            result = analyze_python_test_directory(
                directory=tests_directory,
                openapi_path=openapi_path,
            )

            self.assertEqual(result.files_scanned, 2)
            self.assertEqual(result.requests_discovered, 1)
            self.assertEqual(result.requests_analyzed, 1)
            self.assertEqual(len(result.results), 1)
            self.assertEqual(len(result.scan_errors), 1)
            self.assertEqual(result.analysis_errors, ())

            self.assertEqual(
                result.scan_errors[0].file_path.relative_to(
                    tests_directory
                ),
                Path("test_invalid.py"),
            )


if __name__ == "__main__":
    unittest.main()
