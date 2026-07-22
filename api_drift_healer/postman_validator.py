from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from api_drift_healer.adapters.postman import (
    default_healed_collection_path,
    load_postman_collection,
    patch_postman_request_body,
    write_postman_collection,
)
from api_drift_healer.newman_runner import (
    NewmanRunResult,
    run_newman_collection,
)
from api_drift_healer.postman_healer import (
    PostmanHealResult,
    heal_postman_collection,
)


class PostmanValidationError(ValueError):
    """Raised when runtime validation cannot continue safely."""


PostmanValidationDecision = Literal[
    "NOT_PATCHABLE",
    "ORIGINAL_PASSED",
    "HEALED_FAILED",
    "VALIDATED",
]


@dataclass(frozen=True, slots=True)
class PostmanValidationResult:
    """Result of one Postman healing and Newman validation flow."""

    decision: PostmanValidationDecision
    heal_result: PostmanHealResult
    original_run: NewmanRunResult | None
    healed_run: NewmanRunResult | None
    output_path: Path | None

    @property
    def validated(self) -> bool:
        """Return True only when the healed collection passed Newman."""

        return self.decision == "VALIDATED"

    @property
    def written(self) -> bool:
        """Return True when a validated output file was written."""

        return self.output_path is not None


def _resolve_output_path(
    source_path: Path,
    output_path: str | Path | None,
    *,
    overwrite: bool,
) -> Path:
    """Resolve and validate the final collection output path."""

    target_path = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else default_healed_collection_path(
            source_path
        ).resolve()
    )

    if target_path == source_path:
        raise PostmanValidationError(
            "Validated output must be different from "
            "the source collection."
        )

    if target_path.exists() and not overwrite:
        raise PostmanValidationError(
            f"Output file already exists: {target_path}"
        )

    return target_path


def validate_postman_heal(
    collection_path: str | Path,
    openapi_path: str | Path,
    request_name: str,
    environment_path: str | Path | None = None,
    output_path: str | Path | None = None,
    *,
    overwrite: bool = False,
    timeout_seconds: float = 120.0,
    newman_executable: str | None = None,
    require_original_failure: bool = True,
) -> PostmanValidationResult:
    """Heal one Postman request and validate it with Newman.

    The final output is written only when:

    1. Static drift analysis returns SAFE_PATCH.
    2. The original collection fails Newman, unless that guard is disabled.
    3. The temporarily healed collection passes Newman.
    """

    heal_result = heal_postman_collection(
        collection_path=collection_path,
        openapi_path=openapi_path,
        request_name=request_name,
        dry_run=True,
    )

    analysis = heal_result.analysis

    if not analysis.safe_to_patch:
        return PostmanValidationResult(
            decision="NOT_PATCHABLE",
            heal_result=heal_result,
            original_run=None,
            healed_run=None,
            output_path=None,
        )

    if analysis.old_field is None or analysis.new_field is None:
        raise PostmanValidationError(
            "Safe patch decision does not contain field names."
        )

    source_path = heal_result.source_path

    target_path = _resolve_output_path(
        source_path=source_path,
        output_path=output_path,
        overwrite=overwrite,
    )

    original_run = run_newman_collection(
        collection_path=source_path,
        environment_path=environment_path,
        timeout_seconds=timeout_seconds,
        newman_executable=newman_executable,
    )

    if require_original_failure and original_run.passed:
        return PostmanValidationResult(
            decision="ORIGINAL_PASSED",
            heal_result=heal_result,
            original_run=original_run,
            healed_run=None,
            output_path=None,
        )

    collection = load_postman_collection(source_path)

    patched_collection = patch_postman_request_body(
        collection=collection,
        request_name=request_name,
        old_field=analysis.old_field,
        new_field=analysis.new_field,
    )

    with TemporaryDirectory(
        prefix="api-drift-healer-newman-"
    ) as temporary_directory:
        temporary_path = (
            Path(temporary_directory)
            / "healed.postman_collection.json"
        )

        write_postman_collection(
            collection=patched_collection,
            output_path=temporary_path,
        )

        healed_run = run_newman_collection(
            collection_path=temporary_path,
            environment_path=environment_path,
            timeout_seconds=timeout_seconds,
            newman_executable=newman_executable,
        )

    if healed_run.failed:
        return PostmanValidationResult(
            decision="HEALED_FAILED",
            heal_result=heal_result,
            original_run=original_run,
            healed_run=healed_run,
            output_path=None,
        )

    written_path = write_postman_collection(
        collection=patched_collection,
        output_path=target_path,
        overwrite=overwrite,
    )

    return PostmanValidationResult(
        decision="VALIDATED",
        heal_result=heal_result,
        original_run=original_run,
        healed_run=healed_run,
        output_path=written_path,
    )