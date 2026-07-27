"""Build safe patch plans for Python test directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_drift_healer.python_batch_analyzer import (
    PythonBatchAnalysisResult,
    analyze_python_test_directory,
)
from api_drift_healer.python_diff import (
    PythonDiffError,
    build_python_patch_suggestion,
)


@dataclass(frozen=True, slots=True)
class PythonBatchPatch:
    """One safe in-memory patch generated for a discovered request."""

    file_path: Path
    test_name: str | None
    method: str
    path: str
    old_field: str
    new_field: str
    score: float
    unified_diff: str
    suggested_source: str


@dataclass(frozen=True, slots=True)
class PythonBatchPatchError:
    """An error produced while generating one patch suggestion."""

    file_path: Path
    test_name: str | None
    method: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class PythonBatchPatchPlan:
    """Aggregated analysis and patch suggestions for a test directory."""

    analysis: PythonBatchAnalysisResult
    patches: tuple[PythonBatchPatch, ...]
    patch_errors: tuple[PythonBatchPatchError, ...]


def plan_python_test_directory_patches(
    directory: str | Path,
    openapi_path: str | Path,
) -> PythonBatchPatchPlan:
    """Analyze a test directory and build SAFE_PATCH suggestions only."""

    analysis_result = analyze_python_test_directory(
        directory=directory,
        openapi_path=openapi_path,
    )

    patches: list[PythonBatchPatch] = []
    patch_errors: list[PythonBatchPatchError] = []

    for request_result in analysis_result.results:
        drift_analysis = request_result.analysis

        if not drift_analysis.safe_to_patch:
            continue

        try:
            suggestion = build_python_patch_suggestion(
                request_result
            )
        except PythonDiffError as exc:
            patch_errors.append(
                PythonBatchPatchError(
                    file_path=request_result.source_path,
                    test_name=request_result.request.test_name,
                    method=request_result.normalized_request.method,
                    path=request_result.normalized_request.path,
                    message=str(exc),
                )
            )
            continue

        old_field = drift_analysis.old_field
        new_field = drift_analysis.new_field

        if old_field is None or new_field is None:
            patch_errors.append(
                PythonBatchPatchError(
                    file_path=request_result.source_path,
                    test_name=request_result.request.test_name,
                    method=request_result.normalized_request.method,
                    path=request_result.normalized_request.path,
                    message=(
                        "SAFE_PATCH result did not contain "
                        "both field names."
                    ),
                )
            )
            continue

        patches.append(
            PythonBatchPatch(
                file_path=request_result.source_path,
                test_name=request_result.request.test_name,
                method=request_result.normalized_request.method,
                path=request_result.normalized_request.path,
                old_field=old_field,
                new_field=new_field,
                score=drift_analysis.score,
                unified_diff=suggestion.unified_diff,
                suggested_source=suggestion.suggested_source,
            )
        )

    return PythonBatchPatchPlan(
        analysis=analysis_result,
        patches=tuple(patches),
        patch_errors=tuple(patch_errors),
    )
