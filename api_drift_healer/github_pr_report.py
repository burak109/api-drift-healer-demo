"""Build a safe GitHub pull request comment from a batch report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


COMMENT_MARKER = "<!-- api-drift-healer-report -->"
SUPPORTED_SCHEMA_VERSION = 1

_METRIC_FIELDS = (
    "files_scanned",
    "requests_discovered",
    "requests_analyzed",
    "no_drift",
    "drifts_detected",
    "safe_patch_decisions",
    "rejected_drifts",
    "complex_drifts",
    "patches_generated",
    "patches_validated",
    "validation_failures",
    "pipeline_errors",
)

_METRIC_LABELS = {
    "files_scanned": "Files scanned",
    "requests_discovered": "Requests discovered",
    "requests_analyzed": "Requests analyzed",
    "no_drift": "No drift",
    "drifts_detected": "Drifts detected",
    "safe_patch_decisions": "Safe patch decisions",
    "rejected_drifts": "Rejected drifts",
    "complex_drifts": "Complex drifts",
    "patches_generated": "Patches generated",
    "patches_validated": "Patches validated",
    "validation_failures": "Validation failures",
    "pipeline_errors": "Pipeline errors",
}


class GitHubPullRequestReportError(ValueError):
    """Raised when a batch report cannot be used safely."""


@dataclass(frozen=True, slots=True)
class GitHubPullRequestReport:
    """Validated batch report data for one pull request comment."""

    schema_version: int

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

    source_files_changed: bool


def _required_value(
    payload: Mapping[str, Any],
    field_name: str,
) -> Any:
    """Return one required report field."""

    if field_name not in payload:
        raise GitHubPullRequestReportError(
            f"Missing required report field: {field_name}"
        )

    return payload[field_name]


def _required_non_negative_integer(
    payload: Mapping[str, Any],
    field_name: str,
) -> int:
    """Return one required non-negative integer field."""

    value = _required_value(
        payload,
        field_name,
    )

    if type(value) is not int:
        raise GitHubPullRequestReportError(
            f"Report field must be an integer: {field_name}"
        )

    if value < 0:
        raise GitHubPullRequestReportError(
            f"Report field cannot be negative: {field_name}"
        )

    return value


def build_github_pr_report(
    payload: Mapping[str, Any],
) -> GitHubPullRequestReport:
    """Validate a batch report payload for PR reporting."""

    schema_version = _required_non_negative_integer(
        payload,
        "schema_version",
    )

    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise GitHubPullRequestReportError(
            "Unsupported report schema version: "
            f"{schema_version}"
        )

    source_files_changed = _required_value(
        payload,
        "source_files_changed",
    )

    if type(source_files_changed) is not bool:
        raise GitHubPullRequestReportError(
            "Report field must be a boolean: "
            "source_files_changed"
        )

    metrics = {
        field_name: _required_non_negative_integer(
            payload,
            field_name,
        )
        for field_name in _METRIC_FIELDS
    }

    return GitHubPullRequestReport(
        schema_version=schema_version,
        source_files_changed=source_files_changed,
        **metrics,
    )


def parse_github_pr_report_json(
    content: str,
) -> GitHubPullRequestReport:
    """Parse and validate one JSON batch report."""

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise GitHubPullRequestReportError(
            "Batch report is not valid JSON."
        ) from error

    if not isinstance(payload, dict):
        raise GitHubPullRequestReportError(
            "Batch report JSON must contain an object."
        )

    return build_github_pr_report(payload)


def _report_status(
    report: GitHubPullRequestReport,
) -> str:
    """Return the deterministic PR report status."""

    if report.source_files_changed:
        return "❌ Source-file modification detected"

    if (
        report.pipeline_errors > 0
        or report.validation_failures > 0
    ):
        return "❌ Attention required"

    if report.drifts_detected > 0:
        return "⚠️ API drift detected"

    return "✅ No API drift detected"


def format_github_pr_report(
    report: GitHubPullRequestReport,
) -> str:
    """Format one sticky GitHub pull request comment."""

    lines = [
        COMMENT_MARKER,
        "",
        "## API Drift Healer Report",
        "",
        f"**Status:** {_report_status(report)}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]

    for field_name in _METRIC_FIELDS:
        label = _METRIC_LABELS[field_name]
        value = getattr(
            report,
            field_name,
        )

        lines.append(
            f"| {label} | {value} |"
        )

    changed_text = (
        "Yes"
        if report.source_files_changed
        else "No"
    )

    lines.extend(
        (
            "",
            (
                "Source files changed: "
                f"**{changed_text}**"
            ),
            "",
            (
                "_Detect. Suggest. Report. "
                "Never overwrite._"
            ),
        )
    )

    return "\n".join(lines)


def format_github_pr_report_json(
    content: str,
) -> str:
    """Parse JSON and format one PR report comment."""

    report = parse_github_pr_report_json(
        content
    )

    return format_github_pr_report(
        report
    )
