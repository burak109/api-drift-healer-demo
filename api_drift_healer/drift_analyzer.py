from __future__ import annotations

from api_drift_healer.models import (
    DriftAnalysisResult,
    NormalizedRequest,
    ResolvedRequestSchema,
)
from field_matcher import evaluate_field_match


class DriftAnalyzerError(ValueError):
    """Raised when a request and schema cannot be analyzed together."""


def analyze_request_drift(
    request: NormalizedRequest,
    schema: ResolvedRequestSchema,
) -> DriftAnalysisResult:
    """Analyze a normalized request against an OpenAPI schema."""

    if request.method != schema.method:
        raise DriftAnalyzerError(
            "Request method does not match resolved OpenAPI schema: "
            f"{request.method} != {schema.method}"
        )

    if request.path != schema.path:
        raise DriftAnalyzerError(
            "Request path does not match resolved OpenAPI schema: "
            f"{request.path} != {schema.path}"
        )

    missing_required_fields = tuple(
        field
        for field in schema.required_fields
        if field not in request.body
    )

    invalid_existing_fields = tuple(
        field
        for field in request.body
        if field not in schema.properties
    )

    if not missing_required_fields:
        return DriftAnalysisResult(
            decision="NO_DRIFT",
            request_name=request.name,
            missing_required_fields=(),
            invalid_existing_fields=invalid_existing_fields,
            reasons=(
                "No required OpenAPI fields are missing from the request.",
            ),
        )

    if (
        len(missing_required_fields) != 1
        or len(invalid_existing_fields) != 1
    ):
        return DriftAnalysisResult(
            decision="COMPLEX_DRIFT",
            request_name=request.name,
            missing_required_fields=missing_required_fields,
            invalid_existing_fields=invalid_existing_fields,
            reasons=(
                "Automatic healing requires exactly one missing "
                "required field and one invalid existing field.",
            ),
        )

    old_field = invalid_existing_fields[0]
    new_field = missing_required_fields[0]

    match_decision = evaluate_field_match(
        source_field=old_field,
        target_field=new_field,
        source_value=request.body[old_field],
        target_schema=schema.properties[new_field],
    )

    decision = (
        "SAFE_PATCH"
        if match_decision.safe_to_patch
        else "REJECTED"
    )

    return DriftAnalysisResult(
        decision=decision,
        request_name=request.name,
        missing_required_fields=missing_required_fields,
        invalid_existing_fields=invalid_existing_fields,
        old_field=old_field,
        new_field=new_field,
        score=match_decision.score,
        threshold=match_decision.threshold,
        confidence=match_decision.confidence,
        reasons=tuple(match_decision.reasons),
    )
