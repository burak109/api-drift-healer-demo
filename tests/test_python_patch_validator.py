import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_drift_healer.python_batch_patch_planner import (
    plan_python_test_directory_patches,
)
from api_drift_healer.python_patch_validator import (
    PytestNotAvailableError,
    PythonPatchValidationTimeoutError,
    validate_python_patch,
)


class PythonPatchValidatorTests(unittest.TestCase):
    def _prepare_patch(
        self,
        root: Path,
    ):
        tests_directory = root / "tests"
        tests_directory.mkdir()

        source = '''
import requests


def test_create_user():
    response = requests.post(
        "http://localhost:3000/users",
        json={
            "name": "Test User",
            "userEmail": "qa@example.com",
        },
    )

    assert response.status_code == 201
'''

        source_path = tests_directory / "test_create_user.py"
        source_path.write_text(
            source,
            encoding="utf-8",
        )

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

        openapi_path = root / "openapi.json"
        openapi_path.write_text(
            json.dumps(openapi_document),
            encoding="utf-8",
        )

        plan = plan_python_test_directory_patches(
            directory=tests_directory,
            openapi_path=openapi_path,
        )

        self.assertEqual(len(plan.patches), 1)

        return source_path, source, plan.patches[0]

    @patch(
        "api_drift_healer.python_patch_validator."
        "importlib.util.find_spec"
    )
    @patch(
        "api_drift_healer.python_patch_validator."
        "subprocess.run"
    )
    def test_validates_suggested_source_without_changing_original(
        self,
        run_mock,
        find_spec_mock,
    ) -> None:
        find_spec_mock.return_value = object()
        captured_temp_path = None

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path, original_source, patch_plan = (
                self._prepare_patch(root)
            )

            def fake_run(command, **kwargs):
                nonlocal captured_temp_path

                node_id = command[3]
                temporary_file = node_id.split("::", 1)[0]
                captured_temp_path = Path(temporary_file)

                self.assertTrue(captured_temp_path.exists())

                temporary_source = captured_temp_path.read_text(
                    encoding="utf-8",
                )

                self.assertIn(
                    '"email_address": "qa@example.com"',
                    temporary_source,
                )
                self.assertNotIn(
                    '"userEmail": "qa@example.com"',
                    temporary_source,
                )

                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout="1 passed",
                    stderr="",
                )

            run_mock.side_effect = fake_run

            result = validate_python_patch(
                patch=patch_plan,
                timeout_seconds=5,
            )

            self.assertEqual(result.status, "PASSED")
            self.assertTrue(result.validated)
            self.assertEqual(result.return_code, 0)
            self.assertEqual(result.stdout, "1 passed")

            self.assertEqual(
                source_path.read_text(encoding="utf-8"),
                original_source,
            )

        self.assertIsNotNone(captured_temp_path)
        self.assertFalse(captured_temp_path.exists())

        command = run_mock.call_args.args[0]

        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[1:3], ["-m", "pytest"])
        self.assertIn(
            "::test_create_user",
            command[3],
        )

    @patch(
        "api_drift_healer.python_patch_validator."
        "importlib.util.find_spec"
    )
    @patch(
        "api_drift_healer.python_patch_validator."
        "subprocess.run"
    )
    def test_reports_failed_pytest_validation(
        self,
        run_mock,
        find_spec_mock,
    ) -> None:
        find_spec_mock.return_value = object()
        captured_temp_path = None

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path, original_source, patch_plan = (
                self._prepare_patch(root)
            )

            def fake_run(command, **kwargs):
                nonlocal captured_temp_path

                captured_temp_path = Path(
                    command[3].split("::", 1)[0]
                )

                return subprocess.CompletedProcess(
                    args=command,
                    returncode=1,
                    stdout="",
                    stderr="1 failed",
                )

            run_mock.side_effect = fake_run

            result = validate_python_patch(
                patch=patch_plan,
                timeout_seconds=5,
            )

            self.assertEqual(result.status, "FAILED")
            self.assertFalse(result.validated)
            self.assertEqual(result.return_code, 1)
            self.assertEqual(result.stderr, "1 failed")

            self.assertEqual(
                source_path.read_text(encoding="utf-8"),
                original_source,
            )

        self.assertIsNotNone(captured_temp_path)
        self.assertFalse(captured_temp_path.exists())

    @patch(
        "api_drift_healer.python_patch_validator."
        "importlib.util.find_spec"
    )
    @patch(
        "api_drift_healer.python_patch_validator."
        "subprocess.run"
    )
    def test_cleans_temporary_file_after_timeout(
        self,
        run_mock,
        find_spec_mock,
    ) -> None:
        find_spec_mock.return_value = object()
        captured_temp_path = None

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path, original_source, patch_plan = (
                self._prepare_patch(root)
            )

            def timeout_run(command, **kwargs):
                nonlocal captured_temp_path

                captured_temp_path = Path(
                    command[3].split("::", 1)[0]
                )

                raise subprocess.TimeoutExpired(
                    cmd=command,
                    timeout=5,
                )

            run_mock.side_effect = timeout_run

            with self.assertRaises(
                PythonPatchValidationTimeoutError
            ):
                validate_python_patch(
                    patch=patch_plan,
                    timeout_seconds=5,
                )

            self.assertEqual(
                source_path.read_text(encoding="utf-8"),
                original_source,
            )

        self.assertIsNotNone(captured_temp_path)
        self.assertFalse(captured_temp_path.exists())

    @patch(
        "api_drift_healer.python_patch_validator."
        "importlib.util.find_spec"
    )
    @patch(
        "api_drift_healer.python_patch_validator."
        "subprocess.run"
    )
    def test_reports_when_pytest_is_not_installed(
        self,
        run_mock,
        find_spec_mock,
    ) -> None:
        find_spec_mock.return_value = None

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, _, patch_plan = self._prepare_patch(root)

            with self.assertRaisesRegex(
                PytestNotAvailableError,
                "pytest is not installed",
            ):
                validate_python_patch(
                    patch=patch_plan,
                )

        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
