from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class NewmanRunnerError(RuntimeError):
    """Raised when a Newman collection run cannot be started safely."""


class NewmanNotFoundError(NewmanRunnerError):
    """Raised when the Newman executable cannot be found."""


class NewmanTimeoutError(NewmanRunnerError):
    """Raised when a Newman collection run exceeds its timeout."""


@dataclass(frozen=True, slots=True)
class NewmanRunResult:
    """Result of one Newman collection execution."""

    collection_path: Path
    environment_path: Path | None
    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        """Return True when Newman exits successfully."""

        return self.return_code == 0

    @property
    def failed(self) -> bool:
        """Return True when Newman reports a failed run."""

        return not self.passed


def find_newman_executable() -> str | None:
    """Find the Newman executable on Windows, macOS, or Linux."""

    if os.name == "nt":
        candidates = (
            "newman.cmd",
            "newman.exe",
            "newman",
        )
    else:
        candidates = ("newman",)

    for candidate in candidates:
        executable = shutil.which(candidate)

        if executable is not None:
            return executable

    return None


def _resolve_existing_file(
    file_path: str | Path,
    label: str,
) -> Path:
    """Resolve and validate one required input file."""

    resolved_path = Path(file_path).expanduser().resolve()

    if not resolved_path.exists():
        raise NewmanRunnerError(
            f"{label} does not exist: {resolved_path}"
        )

    if not resolved_path.is_file():
        raise NewmanRunnerError(
            f"{label} must be a file: {resolved_path}"
        )

    return resolved_path


def _build_execution_command(
    command: Sequence[str],
) -> list[str]:
    """Build a subprocess command that also supports npm .cmd shims."""

    if not command:
        raise ValueError("Newman command cannot be empty.")

    executable = command[0].lower()

    if (
        os.name == "nt"
        and executable.endswith((".cmd", ".bat"))
    ):
        command_processor = (
            os.environ.get("COMSPEC")
            or "cmd.exe"
        )

        command_line = subprocess.list2cmdline(
            list(command)
        )

        return [
            command_processor,
            "/d",
            "/s",
            "/c",
            command_line,
        ]

    return list(command)


def run_newman_collection(
    collection_path: str | Path,
    environment_path: str | Path | None = None,
    *,
    timeout_seconds: float = 120.0,
    newman_executable: str | None = None,
) -> NewmanRunResult:
    """Run one Postman collection with Newman.

    A non-zero Newman exit code is returned as a normal result because
    a failed original collection is an expected part of the healing flow.

    Tooling errors such as a missing executable or timeout raise a
    NewmanRunnerError subclass.
    """

    if timeout_seconds <= 0:
        raise ValueError(
            "Newman timeout must be greater than zero."
        )

    resolved_collection = _resolve_existing_file(
        collection_path,
        "Postman collection",
    )

    resolved_environment: Path | None = None

    if environment_path is not None:
        resolved_environment = _resolve_existing_file(
            environment_path,
            "Postman environment",
        )

    executable = (
        newman_executable
        or find_newman_executable()
    )

    if executable is None:
        raise NewmanNotFoundError(
            "Newman executable was not found. "
            "Install Newman and make sure it is available on PATH."
        )

    logical_command = [
        executable,
        "run",
        str(resolved_collection),
    ]

    if resolved_environment is not None:
        logical_command.extend(
            [
                "--environment",
                str(resolved_environment),
            ]
        )

    execution_command = _build_execution_command(
        logical_command
    )

    try:
        completed_process = subprocess.run(
            execution_command,
            cwd=resolved_collection.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise NewmanTimeoutError(
            "Newman run exceeded the timeout of "
            f"{timeout_seconds:g} seconds."
        ) from exc
    except OSError as exc:
        raise NewmanRunnerError(
            f"Newman could not be started: {exc}"
        ) from exc

    return NewmanRunResult(
        collection_path=resolved_collection,
        environment_path=resolved_environment,
        command=tuple(logical_command),
        return_code=completed_process.returncode,
        stdout=completed_process.stdout,
        stderr=completed_process.stderr,
    )