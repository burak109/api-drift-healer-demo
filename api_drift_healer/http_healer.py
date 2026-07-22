from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path

from api_drift_healer.adapters.http_file import (
    default_healed_http_path,
    parse_http_file,
    patch_http_request_body,
    write_http_file,
)
from api_drift_healer.drift_analyzer import (
    analyze_request_drift,
)
from api_drift_healer.models import (
    DriftAnalysisResult,
)
from api_drift_healer.openapi_resolver import (
    resolve_request_schema_file,
)


class HttpHealError(ValueError):
    """Raised when the HTTP healing flow cannot continue safely."""


@dataclass(frozen=True, slots=True)
class HttpHealResult:
    """Result of one complete HTTP file healing attempt."""

    analysis: DriftAnalysisResult
    source_path: Path
    output_path: Path | None
    before_source: str
    after_source: str
    diff: str

    @property
    def written(self) -> bool:
        return self.output_path is not None


def build_http_diff(
    before_source: str,
    after_source: str,
    source_name: str,
) -> str:
    """Build a unified diff without reformatting the HTTP file."""

    return "".join(
        unified_diff(
            before_source.splitlines(
                keepends=True
            ),
            after_source.splitlines(
                keepends=True
            ),
            fromfile=f"{source_name}:before",
            tofile=f"{source_name}:after",
        )
    )


def heal_http_file(
    file_path: str | Path,
    openapi_path: str | Path,
    output_path: str | Path | None = None,
    *,
    dry_run: bool = False,
    overwrite: bool = False,
) -> HttpHealResult:
    """Run the complete format-independent HTTP healing flow."""

    source_path = Path(
        file_path
    ).expanduser().resolve()

    parsed = parse_http_file(source_path)

    schema = resolve_request_schema_file(
        openapi_path=openapi_path,
        method=parsed.request.method,
        path=parsed.request.path,
    )

    analysis = analyze_request_drift(
        request=parsed.request,
        schema=schema,
    )

    before_source = parsed.source_text

    if not analysis.safe_to_patch:
        return HttpHealResult(
            analysis=analysis,
            source_path=source_path,
            output_path=None,
            before_source=before_source,
            after_source=before_source,
            diff="",
        )

    if (
        analysis.old_field is None
        or analysis.new_field is None
    ):
        raise HttpHealError(
            "Safe patch decision does not contain field names."
        )

    after_source = patch_http_request_body(
        parsed_request=parsed,
        old_field=analysis.old_field,
        new_field=analysis.new_field,
    )

    source_diff = build_http_diff(
        before_source=before_source,
        after_source=after_source,
        source_name=source_path.name,
    )

    if dry_run:
        return HttpHealResult(
            analysis=analysis,
            source_path=source_path,
            output_path=None,
            before_source=before_source,
            after_source=after_source,
            diff=source_diff,
        )

    target_path = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else default_healed_http_path(
            source_path
        ).resolve()
    )

    if target_path == source_path:
        raise HttpHealError(
            "Healed output must be different from "
            "the source HTTP file."
        )

    written_path = write_http_file(
        source_text=after_source,
        output_path=target_path,
        overwrite=overwrite,
    )

    return HttpHealResult(
        analysis=analysis,
        source_path=source_path,
        output_path=written_path,
        before_source=before_source,
        after_source=after_source,
        diff=source_diff,
    )