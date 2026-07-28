"""Build aggregate reports for Python batch validation results."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PythonBatchReport:
    """Aggregate statistics for one Python batch pipeline run."""

    files_scanned: int
    requests_discovered: int
    requests_analyzed: int

    no_drift: int
    drifts_detected: int
    safe_patch_decisions: int
    rejected_drifts: int
    complex_drifts: int

    patches_generated: int
    patches_validated: int
    validation_failures: int

    pipeline_errors: int


def _collection_size(value: Any) -> int:
    """Return the size of a collection-like result safely."""

    if value is None:
        return 0

    try:
        return len(value)
    except TypeError:
        return 0


def _decision_name(result: Any) -> str:
    """Extract and normalize a drift decision name."""

    analysis = getattr(
        result,
        "analysis",
        result,
    )

    decision = getattr(
        analysis,
        "decision",
        "",
    )

    if hasattr(decision, "value"):
        decision = decision.value

    return str(decision).strip().upper()


def build_python_batch_report(
    validation_result: Any,
) -> PythonBatchReport:
    """Build aggregate metrics from a batch validation result."""

    plan = validation_result.plan
    batch_analysis = plan.analysis

    decisions = tuple(
        _decision_name(result)
        for result in getattr(
            batch_analysis,
            "results",
            (),
        )
    )

    no_drift = decisions.count("NO_DRIFT")
    safe_patch_decisions = decisions.count(
        "SAFE_PATCH"
    )
    rejected_drifts = decisions.count(
        "REJECTED"
    )
    complex_drifts = decisions.count(
        "COMPLEX_DRIFT"
    )

    drifts_detected = sum(
        decision != "NO_DRIFT"
        for decision in decisions
    )

    validations = tuple(
        getattr(
            validation_result,
            "validations",
            (),
        )
    )

    patches_validated = sum(
        bool(
            getattr(
                validation,
                "validated",
                False,
            )
        )
        for validation in validations
    )

    validation_failures = sum(
        not bool(
            getattr(
                validation,
                "validated",
                False,
            )
        )
        for validation in validations
    )

    pipeline_errors = sum(
        (
            _collection_size(
                getattr(
                    batch_analysis,
                    "scan_errors",
                    (),
                )
            ),
            _collection_size(
                getattr(
                    batch_analysis,
                    "analysis_errors",
                    (),
                )
            ),
            _collection_size(
                getattr(
                    plan,
                    "patch_errors",
                    (),
                )
            ),
            _collection_size(
                getattr(
                    validation_result,
                    "validation_errors",
                    (),
                )
            ),
        )
    )

    return PythonBatchReport(
        files_scanned=getattr(
            batch_analysis,
            "files_scanned",
            0,
        ),
        requests_discovered=getattr(
            batch_analysis,
            "requests_discovered",
            0,
        ),
        requests_analyzed=getattr(
            batch_analysis,
            "requests_analyzed",
            0,
        ),
        no_drift=no_drift,
        drifts_detected=drifts_detected,
        safe_patch_decisions=safe_patch_decisions,
        rejected_drifts=rejected_drifts,
        complex_drifts=complex_drifts,
        patches_generated=_collection_size(
            getattr(
                plan,
                "patches",
                (),
            )
        ),
        patches_validated=patches_validated,
        validation_failures=validation_failures,
        pipeline_errors=pipeline_errors,
    )


def format_python_batch_report(
    report: PythonBatchReport,
) -> str:
    """Format an aggregate report for terminal output."""

    lines = (
        "Python Batch Report",
        "-------------------",
        f"Files scanned: {report.files_scanned}",
        (
            "Requests discovered: "
            f"{report.requests_discovered}"
        ),
        (
            "Requests analyzed: "
            f"{report.requests_analyzed}"
        ),
        f"No drift: {report.no_drift}",
        (
            "Drift detected: "
            f"{report.drifts_detected}"
        ),
        (
            "Safe patch decisions: "
            f"{report.safe_patch_decisions}"
        ),
        (
            "Rejected drift: "
            f"{report.rejected_drifts}"
        ),
        (
            "Complex drift: "
            f"{report.complex_drifts}"
        ),
        (
            "Patches generated: "
            f"{report.patches_generated}"
        ),
        (
            "Patches validated: "
            f"{report.patches_validated}"
        ),
        (
            "Validation failures: "
            f"{report.validation_failures}"
        ),
        (
            "Pipeline errors: "
            f"{report.pipeline_errors}"
        ),
    )

    return "\n".join(lines)


def format_python_batch_report_json(
    report: PythonBatchReport,
) -> str:
    """Format an aggregate report as machine-readable JSON."""

    payload = {
        "schema_version": 1,
        **asdict(report),
        "source_files_changed": False,
    }

    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
    )

def format_python_batch_report_markdown(
    report: PythonBatchReport,
) -> str:
    """Format an aggregate report as GitHub Markdown."""

    lines = (
        "# API Drift Healer Batch Report",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Files scanned | {report.files_scanned} |",
        (
            "| Requests discovered | "
            f"{report.requests_discovered} |"
        ),
        (
            "| Requests analyzed | "
            f"{report.requests_analyzed} |"
        ),
        f"| No drift | {report.no_drift} |",
        (
            "| Drift detected | "
            f"{report.drifts_detected} |"
        ),
        (
            "| Safe patch decisions | "
            f"{report.safe_patch_decisions} |"
        ),
        (
            "| Rejected drift | "
            f"{report.rejected_drifts} |"
        ),
        (
            "| Complex drift | "
            f"{report.complex_drifts} |"
        ),
        (
            "| Patches generated | "
            f"{report.patches_generated} |"
        ),
        (
            "| Patches validated | "
            f"{report.patches_validated} |"
        ),
        (
            "| Validation failures | "
            f"{report.validation_failures} |"
        ),
        (
            "| Pipeline errors | "
            f"{report.pipeline_errors} |"
        ),
        "",
        "Source files changed: **No**",
    )

    return "\n".join(lines)
