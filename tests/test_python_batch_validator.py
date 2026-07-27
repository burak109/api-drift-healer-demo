import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_drift_healer.python_batch_patch_planner import (
    PythonBatchPatch,
    PythonBatchPatchPlan,
)
from api_drift_healer.python_batch_validator import (
    validate_python_test_directory_patches,
)
from api_drift_healer.python_patch_validator import (
    PytestNotAvailableError,
    PythonPatchValidationResult,
    PythonPatchValidationTimeoutError,
)


class PythonBatchValidatorTests(unittest.TestCase):
    def _build_patch(
        self,
        root: Path,
        file_name: str,
        test_name: str,
        method: str,
        path: str,
    ) -> PythonBatchPatch:
        source_path = root / file_name
        source_path.write_text(
            "def test_placeholder():\n    pass\n",
            encoding="utf-8",
        )

        return PythonBatchPatch(
            file_path=source_path.resolve(),
            test_name=test_name,
            method=method,
            path=path,
            old_field="userEmail",
            new_field="email_address",
            score=0.772,
            unified_diff="sample diff",
            suggested_source=(
                "def test_placeholder():\n"
                "    pass\n"
            ),
        )

    def _build_validation(
        self,
        patch_item: PythonBatchPatch,
        status: str,
        return_code: int,
    ) -> PythonPatchValidationResult:
        passed = status == "PASSED"

        return PythonPatchValidationResult(
            file_path=patch_item.file_path,
            test_name=patch_item.test_name or "",
            status=status,
            validated=passed,
            return_code=return_code,
            command=(
                "python",
                "-m",
                "pytest",
            ),
            stdout=(
                "1 passed"
                if passed
                else ""
            ),
            stderr=(
                ""
                if passed
                else "1 failed"
            ),
        )

    @patch(
        "api_drift_healer.python_batch_validator."
        "validate_python_patch"
    )
    @patch(
        "api_drift_healer.python_batch_validator."
        "plan_python_test_directory_patches"
    )
    def test_validates_every_planned_patch(
        self,
        plan_mock,
        validate_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            first_patch = self._build_patch(
                root=root,
                file_name="test_users.py",
                test_name="test_create_user",
                method="POST",
                path="/users",
            )
            second_patch = self._build_patch(
                root=root,
                file_name="test_profiles.py",
                test_name="test_update_profile",
                method="PUT",
                path="/profiles",
            )

            plan = PythonBatchPatchPlan(
                analysis=object(),
                patches=(
                    first_patch,
                    second_patch,
                ),
                patch_errors=(),
            )

            plan_mock.return_value = plan
            validate_mock.side_effect = (
                self._build_validation(
                    first_patch,
                    status="PASSED",
                    return_code=0,
                ),
                self._build_validation(
                    second_patch,
                    status="FAILED",
                    return_code=1,
                ),
            )

            result = validate_python_test_directory_patches(
                directory=root,
                openapi_path=root / "openapi.yaml",
                timeout_seconds=12,
            )

            self.assertIs(result.plan, plan)
            self.assertEqual(len(result.validations), 2)
            self.assertEqual(result.validation_errors, ())
            self.assertEqual(result.patches_validated, 1)

            self.assertEqual(
                tuple(
                    item.status
                    for item in result.validations
                ),
                (
                    "PASSED",
                    "FAILED",
                ),
            )

            self.assertEqual(
                validate_mock.call_count,
                2,
            )

            for call in validate_mock.call_args_list:
                self.assertEqual(
                    call.kwargs["timeout_seconds"],
                    12,
                )

    @patch(
        "api_drift_healer.python_batch_validator."
        "validate_python_patch"
    )
    @patch(
        "api_drift_healer.python_batch_validator."
        "plan_python_test_directory_patches"
    )
    def test_continues_after_one_patch_times_out(
        self,
        plan_mock,
        validate_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            first_patch = self._build_patch(
                root=root,
                file_name="test_users.py",
                test_name="test_create_user",
                method="POST",
                path="/users",
            )
            second_patch = self._build_patch(
                root=root,
                file_name="test_profiles.py",
                test_name="test_update_profile",
                method="PUT",
                path="/profiles",
            )

            plan = PythonBatchPatchPlan(
                analysis=object(),
                patches=(
                    first_patch,
                    second_patch,
                ),
                patch_errors=(),
            )

            plan_mock.return_value = plan
            validate_mock.side_effect = (
                PythonPatchValidationTimeoutError(
                    "Pytest validation exceeded the timeout."
                ),
                self._build_validation(
                    second_patch,
                    status="PASSED",
                    return_code=0,
                ),
            )

            result = validate_python_test_directory_patches(
                directory=root,
                openapi_path=root / "openapi.yaml",
            )

            self.assertEqual(len(result.validations), 1)
            self.assertEqual(result.patches_validated, 1)
            self.assertEqual(len(result.validation_errors), 1)

            error = result.validation_errors[0]

            self.assertEqual(
                error.test_name,
                "test_create_user",
            )
            self.assertEqual(error.method, "POST")
            self.assertEqual(error.path, "/users")
            self.assertIn(
                "timeout",
                error.message.lower(),
            )

            self.assertEqual(
                validate_mock.call_count,
                2,
            )

    @patch(
        "api_drift_healer.python_batch_validator."
        "validate_python_patch"
    )
    @patch(
        "api_drift_healer.python_batch_validator."
        "plan_python_test_directory_patches"
    )
    def test_stops_when_pytest_is_not_available(
        self,
        plan_mock,
        validate_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            first_patch = self._build_patch(
                root=root,
                file_name="test_users.py",
                test_name="test_create_user",
                method="POST",
                path="/users",
            )
            second_patch = self._build_patch(
                root=root,
                file_name="test_profiles.py",
                test_name="test_update_profile",
                method="PUT",
                path="/profiles",
            )

            plan_mock.return_value = PythonBatchPatchPlan(
                analysis=object(),
                patches=(
                    first_patch,
                    second_patch,
                ),
                patch_errors=(),
            )

            validate_mock.side_effect = (
                PytestNotAvailableError(
                    "pytest is not installed"
                )
            )

            with self.assertRaisesRegex(
                PytestNotAvailableError,
                "pytest is not installed",
            ):
                validate_python_test_directory_patches(
                    directory=root,
                    openapi_path=root / "openapi.yaml",
                )

            validate_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
