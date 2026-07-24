import json
import tempfile
import unittest
from pathlib import Path

from api_drift_healer.python_batch_patch_planner import (
    plan_python_test_directory_patches,
)


def build_openapi_document() -> dict:
    schema = {
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
                                "schema": schema,
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
                                "schema": schema,
                            }
                        }
                    }
                }
            },
        },
    }


class PythonBatchPatchPlannerTests(unittest.TestCase):
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

    def test_generates_patches_only_for_safe_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tests_directory = root / "tests"
            openapi_path = self._write_openapi(root)

            safe_source = '''
import requests


def test_create_user():
    requests.post(
        "http://localhost:3000/users",
        json={
            "name": "Safe User",
            "userEmail": "safe@example.com",
        },
    )
'''

            no_drift_source = '''
import requests


def test_update_profile():
    requests.put(
        "http://localhost:3000/profiles",
        json={
            "name": "Current User",
            "email_address": "current@example.com",
        },
    )
'''

            rejected_source = '''
import requests


def test_rejected_user():
    requests.post(
        "http://localhost:3000/users",
        json={
            "name": "Rejected User",
            "displayName": "Burak",
        },
    )
'''

            safe_path = self._write_file(
                tests_directory,
                "test_create_user.py",
                safe_source,
            )
            self._write_file(
                tests_directory,
                "test_profile.py",
                no_drift_source,
            )
            self._write_file(
                tests_directory,
                "test_rejected.py",
                rejected_source,
            )

            result = plan_python_test_directory_patches(
                directory=tests_directory,
                openapi_path=openapi_path,
            )

            self.assertEqual(
                result.analysis.files_scanned,
                3,
            )
            self.assertEqual(
                result.analysis.requests_analyzed,
                3,
            )
            self.assertEqual(len(result.patches), 1)
            self.assertEqual(result.patch_errors, ())

            patch = result.patches[0]

            self.assertEqual(
                patch.file_path,
                safe_path.resolve(),
            )
            self.assertEqual(
                patch.test_name,
                "test_create_user",
            )
            self.assertEqual(patch.method, "POST")
            self.assertEqual(patch.path, "/users")
            self.assertEqual(
                patch.old_field,
                "userEmail",
            )
            self.assertEqual(
                patch.new_field,
                "email_address",
            )
            self.assertAlmostEqual(
                patch.score,
                0.772,
                places=3,
            )
            self.assertIn(
                '-            "userEmail": "safe@example.com",',
                patch.unified_diff,
            )
            self.assertIn(
                '+            "email_address": "safe@example.com",',
                patch.unified_diff,
            )

            self.assertEqual(
                safe_path.read_text(encoding="utf-8"),
                safe_source,
            )

    def test_generates_multiple_patches_from_one_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tests_directory = root / "tests"
            openapi_path = self._write_openapi(root)

            source = '''
import requests


def test_create_user():
    requests.post(
        "http://localhost:3000/users",
        json={
            "name": "Create User",
            "userEmail": "create@example.com",
        },
    )


def test_update_profile():
    requests.put(
        "http://localhost:3000/profiles",
        json={
            "name": "Profile User",
            "userEmail": "profile@example.com",
        },
    )
'''

            source_path = self._write_file(
                tests_directory,
                "test_multiple_requests.py",
                source,
            )

            result = plan_python_test_directory_patches(
                directory=tests_directory,
                openapi_path=openapi_path,
            )

            self.assertEqual(len(result.patches), 2)
            self.assertEqual(result.patch_errors, ())

            self.assertEqual(
                tuple(
                    patch.test_name
                    for patch in result.patches
                ),
                (
                    "test_create_user",
                    "test_update_profile",
                ),
            )

            self.assertEqual(
                tuple(
                    patch.method
                    for patch in result.patches
                ),
                (
                    "POST",
                    "PUT",
                ),
            )

            self.assertEqual(
                tuple(
                    patch.path
                    for patch in result.patches
                ),
                (
                    "/users",
                    "/profiles",
                ),
            )

            self.assertIn(
                "create@example.com",
                result.patches[0].unified_diff,
            )
            self.assertIn(
                "profile@example.com",
                result.patches[1].unified_diff,
            )

            self.assertEqual(
                source_path.read_text(encoding="utf-8"),
                source,
            )

    def test_continues_when_one_patch_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tests_directory = root / "tests"
            openapi_path = self._write_openapi(root)

            self._write_file(
                tests_directory,
                "a_ambiguous_test.py",
                '''
import requests


def test_ambiguous():
    requests.post(
        "http://localhost:3000/users",
        json={
            "name": "Ambiguous User",
            "userEmail": "first@example.com",
            "userEmail": "second@example.com",
        },
    )
''',
            )

            self._write_file(
                tests_directory,
                "z_valid_test.py",
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

            result = plan_python_test_directory_patches(
                directory=tests_directory,
                openapi_path=openapi_path,
            )

            self.assertEqual(
                result.analysis.requests_analyzed,
                2,
            )
            self.assertEqual(len(result.patches), 1)
            self.assertEqual(len(result.patch_errors), 1)

            self.assertEqual(
                result.patches[0].test_name,
                "test_valid",
            )

            error = result.patch_errors[0]

            self.assertEqual(
                error.test_name,
                "test_ambiguous",
            )
            self.assertIn(
                "appears more than once",
                error.message,
            )


if __name__ == "__main__":
    unittest.main()
