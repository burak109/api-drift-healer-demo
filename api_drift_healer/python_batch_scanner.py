"""Collect requests from multiple Python test files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_drift_healer.python_parser import (
    PythonParseError,
    PythonRequest,
    parse_python_file,
)
from api_drift_healer.python_test_scanner import (
    scan_python_test_files,
)


@dataclass(frozen=True)
class ScannedPythonRequest:
    """A parsed request together with its source file."""

    file_path: Path
    request: PythonRequest


@dataclass(frozen=True)
class PythonBatchScanError:
    """An error produced while scanning one Python test file."""

    file_path: Path
    message: str


@dataclass(frozen=True)
class PythonBatchScanResult:
    """Aggregated result for a directory of Python tests."""

    files_scanned: int
    requests: tuple[ScannedPythonRequest, ...]
    errors: tuple[PythonBatchScanError, ...]


def scan_python_test_requests(
    directory: str | Path,
) -> PythonBatchScanResult:
    """Scan test files and collect supported requests.

    A parse error in one file does not stop the remaining files
    from being analyzed.
    """

    test_files = scan_python_test_files(directory)

    discovered_requests: list[ScannedPythonRequest] = []
    errors: list[PythonBatchScanError] = []

    for file_path in test_files:
        try:
            parse_result = parse_python_file(file_path)
        except PythonParseError as exc:
            errors.append(
                PythonBatchScanError(
                    file_path=file_path,
                    message=str(exc),
                )
            )
            continue

        for request in parse_result.requests:
            discovered_requests.append(
                ScannedPythonRequest(
                    file_path=file_path,
                    request=request,
                )
            )

    return PythonBatchScanResult(
        files_scanned=len(test_files),
        requests=tuple(discovered_requests),
        errors=tuple(errors),
    )
