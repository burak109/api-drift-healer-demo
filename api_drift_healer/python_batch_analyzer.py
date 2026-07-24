"""Analyze requests discovered across multiple Python test files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_drift_healer.python_batch_scanner import (
    PythonBatchScanError,
    scan_python_test_requests,
)
from api_drift_healer.python_parser import PythonRequest
from api_drift_healer.python_request_analyzer import (
    PythonRequestAnalysisResult,
    analyze_python_request,
)


@dataclass(frozen=True)
class PythonBatchAnalysisError:
    """An error produced while analyzing one discovered request."""

    file_path: Path
    request: PythonRequest
    message: str


@dataclass(frozen=True)
class PythonBatchAnalysisResult:
    """Aggregated drift results for a Python test directory."""

    files_scanned: int
    requests_discovered: int
    requests_analyzed: int
    results: tuple[PythonRequestAnalysisResult, ...]
    scan_errors: tuple[PythonBatchScanError, ...]
    analysis_errors: tuple[PythonBatchAnalysisError, ...]


def analyze_python_test_directory(
    directory: str | Path,
    openapi_path: str | Path,
) -> PythonBatchAnalysisResult:
    """Analyze every supported request found in a test directory."""

    scan_result = scan_python_test_requests(directory)

    analysis_results: list[
        PythonRequestAnalysisResult
    ] = []

    analysis_errors: list[
        PythonBatchAnalysisError
    ] = []

    for scanned_request in scan_result.requests:
        try:
            result = analyze_python_request(
                source_path=scanned_request.file_path,
                request=scanned_request.request,
                openapi_path=openapi_path,
            )
        except ValueError as exc:
            analysis_errors.append(
                PythonBatchAnalysisError(
                    file_path=scanned_request.file_path,
                    request=scanned_request.request,
                    message=str(exc),
                )
            )
            continue

        analysis_results.append(result)

    return PythonBatchAnalysisResult(
        files_scanned=scan_result.files_scanned,
        requests_discovered=len(scan_result.requests),
        requests_analyzed=len(analysis_results),
        results=tuple(analysis_results),
        scan_errors=scan_result.errors,
        analysis_errors=tuple(analysis_errors),
    )
