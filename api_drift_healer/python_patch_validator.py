"""Validate an in-memory Python patch with targeted pytest execution."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from api_drift_healer.python_batch_patch_planner import (
    PythonBatchPatch,
)


class PythonPatchValidationError(ValueError):
    """Raised when a Python patch cannot be validated safely."""


class PytestNotAvailableError(PythonPatchValidationError):
    """Raised when pytest is unavailable in the active Python environment."""


class PythonPatchValidationTimeoutError(
    PythonPatchValidationError
):
    """Raised when targeted pytest validation exceeds its timeout."""


@dataclass(frozen=True, slots=True)
class PythonPatchValidationResult:
    """Result of targeted validation for one suggested patch."""

    file_path: Path
    test_name: str
    status: str
    validated: bool
    return_code: int
    command: tuple[str, ...]
    stdout: str
    stderr: str


def validate_python_patch(
    patch: PythonBatchPatch,
    timeout_seconds: float = 30,
) -> PythonPatchValidationResult:
    """
    Validate one suggested patch using a temporary sibling test file.

    The original Python source file is never modified.
    """

    if timeout_seconds <= 0:
        raise PythonPatchValidationError(
            "Validation timeout must be greater than zero."
        )

    if importlib.util.find_spec("pytest") is None:
        raise PytestNotAvailableError(
            "pytest is not installed in the active Python environment."
        )

    if not patch.test_name:
        raise PythonPatchValidationError(
            "Targeted validation requires a pytest test function name."
        )

    source_path = patch.file_path.expanduser().resolve()

    if not source_path.exists():
        raise PythonPatchValidationError(
            f"Python source does not exist: {source_path}"
        )

    if not source_path.is_file():
        raise PythonPatchValidationError(
            f"Python source path is not a file: {source_path}"
        )

    temporary_path: Path | None = None

    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".api_drift_healer_{source_path.stem}_",
            suffix=".py",
            dir=source_path.parent,
            text=True,
        )

        temporary_path = Path(temporary_name)

        with os.fdopen(
            file_descriptor,
            mode="w",
            encoding="utf-8",
            newline="",
        ) as temporary_file:
            temporary_file.write(
                patch.suggested_source
            )

        node_id = (
            f"{temporary_path}"
            f"::{patch.test_name}"
        )

        command = [
            sys.executable,
            "-m",
            "pytest",
            node_id,
            "-q",
        ]

        try:
            completed_process = subprocess.run(
                command,
                cwd=source_path.parent,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PythonPatchValidationTimeoutError(
                "Pytest validation exceeded the timeout of "
                f"{timeout_seconds:g} seconds."
            ) from exc
        except OSError as exc:
            raise PythonPatchValidationError(
                f"Pytest validation could not be started: {exc}"
            ) from exc

        passed = completed_process.returncode == 0

        return PythonPatchValidationResult(
            file_path=source_path,
            test_name=patch.test_name,
            status=(
                "PASSED"
                if passed
                else "FAILED"
            ),
            validated=passed,
            return_code=completed_process.returncode,
            command=tuple(command),
            stdout=completed_process.stdout,
            stderr=completed_process.stderr,
        )

    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            try:
                temporary_path.unlink()
            except OSError:
                pass
