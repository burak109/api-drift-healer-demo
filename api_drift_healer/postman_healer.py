from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Any

from api_drift_healer.adapters.postman import (
    default_healed_collection_path,
    load_postman_collection,
    normalize_postman_request,
    patch_postman_request_body,
    write_postman_collection,
)
from api_drift_healer.drift_analyzer import analyze_request_drift
from api_drift_healer.models import DriftAnalysisResult
from api_drift_healer.openapi_resolver import (
    resolve_request_schema_file,
)


class PostmanHealError(ValueError):
    """Raised when the Postman healing flow cannot continue safely."""


@dataclass(frozen=True, slots=True)
class PostmanHealResult:
    """Result of one complete Postman healing attempt."""

    analysis: DriftAnalysisResult
    source_path: Path
    output_path: Path | None
    before_body: dict[str, Any]
    after_body: dict[str, Any]
    diff: str

    @property
    def written(self) -> bool:
        return self.output_path is not None


def build_body_diff(
    before_body: dict[str, Any],
    after_body: dict[str, Any],
    request_name: str,
) -> str:
    """Build a unified diff for a Postman JSON request body."""

    before_text = (
        json.dumps(
            before_body,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    after_text = (
        json.dumps(
            after_body,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    return "".join(
        unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=f"{request_name}:before",
            tofile=f"{request_name}:after",
        )
    )


def heal_postman_collection(
    collection_path: str | Path,
    openapi_path: str | Path,
    request_name: str,
    output_path: str | Path | None = None,
    *,
    dry_run: bool = False,
    overwrite: bool = False,
) -> PostmanHealResult:
    """Run the complete format-independent Postman healing flow."""

    source_path = Path(
        collection_path
    ).expanduser().resolve()

    collection = load_postman_collection(source_path)

    request = normalize_postman_request(
        collection=collection,
        request_name=request_name,
    )

    schema = resolve_request_schema_file(
        openapi_path=openapi_path,
        method=request.method,
        path=request.path,
    )

    analysis = analyze_request_drift(
        request=request,
        schema=schema,
    )

    before_body = dict(request.body)

    if not analysis.safe_to_patch:
        return PostmanHealResult(
            analysis=analysis,
            source_path=source_path,
            output_path=None,
            before_body=before_body,
            after_body=before_body,
            diff="",
        )

    if analysis.old_field is None or analysis.new_field is None:
        raise PostmanHealError(
            "Safe patch decision does not contain field names."
        )

    patched_collection = patch_postman_request_body(
        collection=collection,
        request_name=request_name,
        old_field=analysis.old_field,
        new_field=analysis.new_field,
    )

    patched_request = normalize_postman_request(
        collection=patched_collection,
        request_name=request_name,
    )

    after_body = dict(patched_request.body)

    body_diff = build_body_diff(
        before_body=before_body,
        after_body=after_body,
        request_name=request_name,
    )

    if dry_run:
        return PostmanHealResult(
            analysis=analysis,
            source_path=source_path,
            output_path=None,
            before_body=before_body,
            after_body=after_body,
            diff=body_diff,
        )

    target_path = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else default_healed_collection_path(
            source_path
        ).resolve()
    )

    if target_path == source_path:
        raise PostmanHealError(
            "Healed output must be different from "
            "the source collection."
        )

    written_path = write_postman_collection(
        collection=patched_collection,
        output_path=target_path,
        overwrite=overwrite,
    )

    return PostmanHealResult(
        analysis=analysis,
        source_path=source_path,
        output_path=written_path,
        before_body=before_body,
        after_body=after_body,
        diff=body_diff,
    )
