"""Validate every safe patch planned for a Python test directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_drift_healer.python_batch_patch_planner import (
    PythonBatchPatchPlan,
    plan_python_test_directory_patches,
)
from api_drift_healer.python_patch_validator import (
    PytestNotAvailableError,
    PythonPatchValidationError,
    PythonPatchValidationResult,
    validate_python_patch,
)


@dataclass(frozen=True, slots=True)
class PythonBatchValidationError:
    """An error produced while validating one planned patch."""

    file_path: Path
    test_name: str | None
    method: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class PythonBatchValidationResult:
    """Aggregated validation results for one Python test directory."""

    plan: PythonBatchPatchPlan
    validations: tuple[PythonPatchValidationResult, ...]
    validation_errors: tuple[PythonBatchValidationError, ...]

    @property
    def patches_validated(self) -> int:
        """Return the number of patches whose targeted test passed."""

        return sum(
            validation.validated
            for validation in self.validations
        )


def validate_python_test_directory_patches(
    directory: str | Path,
    openapi_path: str | Path,
    timeout_seconds: float = 30,
) -> PythonBatchValidationResult:
    """Plan and validate every safe patch found in a test directory."""

    plan = plan_python_test_directory_patches(
        directory=directory,
        openapi_path=openapi_path,
    )

    validations: list[PythonPatchValidationResult] = []
    validation_errors: list[PythonBatchValidationError] = []

    for patch in plan.patches:
        try:
            validation = validate_python_patch(
                patch=patch,
                timeout_seconds=timeout_seconds,
            )
        except PytestNotAvailableError:
            # Pytest availability is an environment-wide problem.
            # Retrying the remaining patches would produce the same error.
            raise
        except PythonPatchValidationError as exc:
            validation_errors.append(
                PythonBatchValidationError(
                    file_path=patch.file_path,
                    test_name=patch.test_name,
                    method=patch.method,
                    path=patch.path,
                    message=str(exc),
                )
            )
            continue

        validations.append(validation)

    return PythonBatchValidationResult(
        plan=plan,
        validations=tuple(validations),
        validation_errors=tuple(validation_errors),
    )
