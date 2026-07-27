from pathlib import Path
from typing import Optional

import typer

from api_drift_healer.adapters.http_file import (
    HttpFileParseError,
    HttpFilePatchError,
)
from api_drift_healer.adapters.postman import PostmanAdapterError
from api_drift_healer.drift_analyzer import DriftAnalyzerError
from api_drift_healer.http_healer import (
    HttpHealError,
    heal_http_file,
)
from api_drift_healer.newman_runner import (
    NewmanRunResult,
    NewmanRunnerError,
)
from api_drift_healer.openapi_resolver import OpenApiResolverError
from api_drift_healer.postman_healer import (
    PostmanHealError,
    heal_postman_collection,
)
from api_drift_healer.postman_validator import (
    PostmanValidationError,
    validate_postman_heal,
)
from api_drift_healer.python_diff import (
    PythonDiffError,
    build_python_patch_suggestion,
)
from api_drift_healer.python_batch_report import (
    build_python_batch_report,
    format_python_batch_report,
)
from api_drift_healer.python_batch_validator import (
    validate_python_test_directory_patches,
)
from api_drift_healer.python_patch_validator import (
    PytestNotAvailableError,
    PythonPatchValidationError,
)
from api_drift_healer.python_request_analyzer import (
    PythonRequestAnalysisError,
    analyze_python_request_file,
)
from auto_healer import run_healer


app = typer.Typer(
    name="api-drift-healer",
    help=(
        "Detect and safely heal API contract drift "
        "in YAML tests, Postman collections, .http files, "
        "and Python requests tests."
    ),
    no_args_is_help=True,
)

postman_app = typer.Typer(
    help="Auto-heal Postman collections from OpenAPI drift.",
    no_args_is_help=True,
)

http_app = typer.Typer(
    help="Auto-heal .http request files from OpenAPI drift.",
    no_args_is_help=True,
)

pytest_app = typer.Typer(
    help=(
        "Detect stale payload fields in pytest and "
        "Python requests API tests."
    ),
    no_args_is_help=True,
)

app.add_typer(
    postman_app,
    name="postman",
)

app.add_typer(
    http_app,
    name="http",
)

app.add_typer(
    pytest_app,
    name="pytest",
)


@app.callback()
def main() -> None:
    """Detect and safely heal API contract drift."""


@app.command()
def heal(
    test: Path = typer.Option(
        ...,
        "--test",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the YAML API test file.",
    ),
    openapi: Path = typer.Option(
        ...,
        "--openapi",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the OpenAPI contract file.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Path for the generated healed test file.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Analyze drift without writing files.",
    ),
    apply_patch: bool = typer.Option(
        False,
        "--apply",
        help="Apply the validated patch to the original test file.",
    ),
    create_pr: bool = typer.Option(
        False,
        "--create-pr",
        help="Open a pull request after a validated apply.",
    ),
) -> None:
    """Analyze and heal API contract drift in a YAML test."""

    if dry_run and apply_patch:
        raise typer.BadParameter(
            "--dry-run cannot be used together with --apply."
        )

    if dry_run and create_pr:
        raise typer.BadParameter(
            "--dry-run cannot be used together with --create-pr."
        )

    if create_pr and not apply_patch:
        raise typer.BadParameter(
            "--create-pr requires --apply."
        )

    resolved_output = output or test.with_name(
        f"{test.stem}.healed{test.suffix}"
    )

    report_file = resolved_output.with_name(
        "heal_report.md"
    )

    if dry_run:
        mode = "DRY RUN"
    elif create_pr:
        mode = "APPLY + CREATE PR"
    elif apply_patch:
        mode = "APPLY"
    else:
        mode = "HEAL"

    typer.echo("API Drift Healer V1.0 YAML CLI")
    typer.echo(f"Test file: {test}")
    typer.echo(f"OpenAPI file: {openapi}")
    typer.echo(f"Output file: {resolved_output}")
    typer.echo(f"Mode: {mode}")
    typer.echo("")

    exit_code = run_healer(
        test_case_file=test,
        openapi_file=openapi,
        healed_test_file=resolved_output,
        report_file=report_file,
        create_pr=create_pr,
        dry_run=dry_run,
        apply_patch=apply_patch,
    )

    raise typer.Exit(code=exit_code)


def echo_newman_result(
    label: str,
    result: Optional[NewmanRunResult],
) -> None:
    """Print a concise Newman runtime result."""

    if result is None:
        return

    if result.passed:
        status = "PASS"
    else:
        status = f"FAIL (exit code {result.return_code})"

    typer.echo(f"{label}: {status}")


@postman_app.command("heal")
def heal_postman(
    collection: Path = typer.Option(
        ...,
        "--collection",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the Postman Collection v2.1 JSON file.",
    ),
    request_name: str = typer.Option(
        ...,
        "--request",
        help="Exact name of the Postman request to analyze.",
    ),
    openapi: Path = typer.Option(
        ...,
        "--openapi",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the OpenAPI contract file.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Path for the healed Postman collection.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Analyze and show the diff without writing a file.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow an existing output file to be replaced.",
    ),
    validate_newman: bool = typer.Option(
        False,
        "--validate-newman",
        help=(
            "Run the original and healed collections with Newman. "
            "The output is written only when the healed run passes."
        ),
    ),
    environment: Optional[Path] = typer.Option(
        None,
        "--environment",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Optional Postman environment JSON file for Newman.",
    ),
    newman_timeout: float = typer.Option(
        120.0,
        "--newman-timeout",
        min=0.1,
        help="Maximum Newman runtime in seconds.",
    ),
    allow_original_pass: bool = typer.Option(
        False,
        "--allow-original-pass",
        help=(
            "Allow validation to continue even when the original "
            "collection already passes Newman."
        ),
    ),
) -> None:
    """Auto-heal one Postman request from OpenAPI drift."""

    if dry_run and validate_newman:
        raise typer.BadParameter(
            "--dry-run cannot be used together with "
            "--validate-newman."
        )

    if environment is not None and not validate_newman:
        raise typer.BadParameter(
            "--environment requires --validate-newman."
        )

    if allow_original_pass and not validate_newman:
        raise typer.BadParameter(
            "--allow-original-pass requires --validate-newman."
        )

    if validate_newman:
        mode = "NEWMAN VALIDATION"
    elif dry_run:
        mode = "DRY RUN"
    else:
        mode = "HEAL"

    typer.echo("API Drift Healer V1.2 Postman CLI")
    typer.echo(f"Collection: {collection}")
    typer.echo(f"Request: {request_name}")
    typer.echo(f"OpenAPI: {openapi}")

    if output is not None:
        typer.echo(f"Output: {output}")

    if environment is not None:
        typer.echo(f"Environment: {environment}")

    if validate_newman:
        typer.echo(
            f"Newman timeout: {newman_timeout:g} seconds"
        )

    typer.echo(f"Mode: {mode}")
    typer.echo("")

    if validate_newman:
        try:
            validation_result = validate_postman_heal(
                collection_path=collection,
                openapi_path=openapi,
                request_name=request_name,
                environment_path=environment,
                output_path=output,
                overwrite=overwrite,
                timeout_seconds=newman_timeout,
                require_original_failure=(
                    not allow_original_pass
                ),
            )
        except (
            PostmanAdapterError,
            OpenApiResolverError,
            DriftAnalyzerError,
            PostmanHealError,
            PostmanValidationError,
            NewmanRunnerError,
        ) as exc:
            typer.echo(
                f"[ERROR] {exc}",
                err=True,
            )
            raise typer.Exit(code=2) from exc

        heal_result = validation_result.heal_result
        analysis = heal_result.analysis

        typer.echo(
            f"Static analysis: {analysis.decision}"
        )

        if (
            analysis.old_field is not None
            and analysis.new_field is not None
        ):
            typer.echo(
                "Candidate: "
                f"{analysis.old_field} -> "
                f"{analysis.new_field}"
            )

        if analysis.score is not None:
            typer.echo(
                f"Score: {analysis.score:.3f}"
            )

        if analysis.threshold is not None:
            typer.echo(
                f"Threshold: {analysis.threshold:.3f}"
            )

        if analysis.confidence is not None:
            typer.echo(
                f"Confidence: {analysis.confidence}"
            )

        if heal_result.diff:
            typer.echo("")
            typer.echo("Diff:")
            typer.echo(
                heal_result.diff.rstrip("\n")
            )

        typer.echo("")

        echo_newman_result(
            "Original Newman",
            validation_result.original_run,
        )

        echo_newman_result(
            "Healed Newman",
            validation_result.healed_run,
        )

        typer.echo(
            f"Decision: {validation_result.decision}"
        )

        if validation_result.decision == "VALIDATED":
            typer.echo("")

            if validation_result.output_path is not None:
                typer.echo(
                    "[+] Validated Postman collection generated: "
                    f"{validation_result.output_path}"
                )

            raise typer.Exit(code=0)

        if validation_result.decision == "ORIGINAL_PASSED":
            typer.echo("")
            typer.echo(
                "[!] The original collection already passed Newman."
            )
            typer.echo(
                "Validated output was not written."
            )
            typer.echo(
                "Use --allow-original-pass to continue "
                "validation anyway."
            )

            raise typer.Exit(code=1)

        if validation_result.decision == "HEALED_FAILED":
            typer.echo("")
            typer.echo(
                "[!] The healed collection failed Newman."
            )
            typer.echo(
                "Validated output was not written."
            )

            if (
                validation_result.healed_run is not None
                and validation_result.healed_run.stdout.strip()
            ):
                typer.echo("")
                typer.echo("Newman output:")
                typer.echo(
                    validation_result.healed_run.stdout.rstrip()
                )

            if (
                validation_result.healed_run is not None
                and validation_result.healed_run.stderr.strip()
            ):
                typer.echo("")
                typer.echo(
                    validation_result.healed_run.stderr.rstrip(),
                    err=True,
                )

            raise typer.Exit(code=1)

        if validation_result.decision == "NOT_PATCHABLE":
            typer.echo("")

            if analysis.decision == "NO_DRIFT":
                typer.echo(
                    "No missing required OpenAPI fields "
                    "were found."
                )
                raise typer.Exit(code=0)

            typer.echo(
                "[!] Automatic Postman patch was not applied."
            )

            for reason in analysis.reasons:
                typer.echo(f"    - {reason}")

            raise typer.Exit(code=1)

        typer.echo(
            "[ERROR] Unknown Newman validation decision.",
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        result = heal_postman_collection(
            collection_path=collection,
            openapi_path=openapi,
            request_name=request_name,
            output_path=output,
            dry_run=dry_run,
            overwrite=overwrite,
        )
    except (
        PostmanAdapterError,
        OpenApiResolverError,
        DriftAnalyzerError,
        PostmanHealError,
    ) as exc:
        typer.echo(
            f"[ERROR] {exc}",
            err=True,
        )
        raise typer.Exit(code=2) from exc

    analysis = result.analysis

    typer.echo(f"Decision: {analysis.decision}")

    if (
        analysis.old_field is not None
        and analysis.new_field is not None
    ):
        typer.echo(
            "Candidate: "
            f"{analysis.old_field} -> "
            f"{analysis.new_field}"
        )

    if analysis.score is not None:
        typer.echo(
            f"Score: {analysis.score:.3f}"
        )

    if analysis.threshold is not None:
        typer.echo(
            f"Threshold: {analysis.threshold:.3f}"
        )

    if analysis.confidence is not None:
        typer.echo(
            f"Confidence: {analysis.confidence}"
        )

    if result.diff:
        typer.echo("")
        typer.echo("Diff:")
        typer.echo(
            result.diff.rstrip("\n")
        )

    if analysis.decision == "SAFE_PATCH":
        if dry_run:
            typer.echo("")
            typer.echo(
                "[DRY RUN] Safe patch found. "
                "No collection file was written."
            )
        elif result.output_path is not None:
            typer.echo("")
            typer.echo(
                "[+] Healed collection generated: "
                f"{result.output_path}"
            )

        raise typer.Exit(code=0)

    if analysis.decision == "NO_DRIFT":
        typer.echo("")
        typer.echo(
            "No missing required OpenAPI fields were found."
        )
        raise typer.Exit(code=0)

    typer.echo("")
    typer.echo(
        "[!] Automatic Postman patch was not applied."
    )

    for reason in analysis.reasons:
        typer.echo(f"    - {reason}")

    raise typer.Exit(code=1)


@http_app.command("heal")
def heal_http(
    file: Path = typer.Option(
        ...,
        "--file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the single-request .http file.",
    ),
    openapi: Path = typer.Option(
        ...,
        "--openapi",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the OpenAPI contract file.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Path for the healed .http file.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Analyze and show the diff without writing a file.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow an existing output file to be replaced.",
    ),
) -> None:
    """Auto-heal one request from a .http file."""

    mode = "DRY RUN" if dry_run else "HEAL"

    typer.echo("API Drift Healer V1.1 HTTP File CLI")
    typer.echo(f"HTTP file: {file}")
    typer.echo(f"OpenAPI: {openapi}")

    if output is not None:
        typer.echo(f"Output: {output}")

    typer.echo(f"Mode: {mode}")
    typer.echo("")

    try:
        result = heal_http_file(
            file_path=file,
            openapi_path=openapi,
            output_path=output,
            dry_run=dry_run,
            overwrite=overwrite,
        )
    except (
        HttpFileParseError,
        HttpFilePatchError,
        OpenApiResolverError,
        DriftAnalyzerError,
        HttpHealError,
    ) as exc:
        typer.echo(
            f"[ERROR] {exc}",
            err=True,
        )
        raise typer.Exit(code=2) from exc

    analysis = result.analysis

    typer.echo(f"Decision: {analysis.decision}")

    if (
        analysis.old_field is not None
        and analysis.new_field is not None
    ):
        typer.echo(
            f"Candidate: "
            f"{analysis.old_field} -> {analysis.new_field}"
        )

    if analysis.score is not None:
        typer.echo(
            f"Score: {analysis.score:.3f}"
        )

    if analysis.threshold is not None:
        typer.echo(
            f"Threshold: {analysis.threshold:.3f}"
        )

    if analysis.confidence is not None:
        typer.echo(
            f"Confidence: {analysis.confidence}"
        )

    if result.diff:
        typer.echo("")
        typer.echo("Diff:")
        typer.echo(
            result.diff.rstrip("\n")
        )

    if analysis.decision == "SAFE_PATCH":
        if dry_run:
            typer.echo("")
            typer.echo(
                "[DRY RUN] Safe patch found. "
                "No HTTP file was written."
            )
        elif result.output_path is not None:
            typer.echo("")
            typer.echo(
                f"[+] Healed HTTP file generated: "
                f"{result.output_path}"
            )

        raise typer.Exit(code=0)

    if analysis.decision == "NO_DRIFT":
        typer.echo("")
        typer.echo(
            "No missing required OpenAPI fields were found."
        )
        raise typer.Exit(code=0)

    typer.echo("")
    typer.echo(
        "[!] Automatic HTTP file patch was not applied."
    )

    for reason in analysis.reasons:
        typer.echo(f"    - {reason}")

    raise typer.Exit(code=1)


@pytest_app.command("analyze")
def analyze_pytest_request(
    file: Path = typer.Option(
        ...,
        "--file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the Python API test file.",
    ),
    openapi: Path = typer.Option(
        ...,
        "--openapi",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the OpenAPI contract file.",
    ),
) -> None:
    """
    Analyze one Python requests call and show a safe patch suggestion.

    The Python source file is never modified.
    """

    typer.echo("")
    typer.echo(
        "API Drift Healer - Pytest / Requests Adapter"
    )
    typer.echo("")
    typer.echo(f"Python file : {file}")
    typer.echo(f"OpenAPI    : {openapi}")
    typer.echo("Mode       : SUGGEST_ONLY")
    typer.echo("")

    try:
        result = analyze_python_request_file(
            python_path=file,
            openapi_path=openapi,
        )
    except (
        PythonRequestAnalysisError,
        OpenApiResolverError,
        DriftAnalyzerError,
    ) as exc:
        typer.echo(
            f"Analysis error: {exc}",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    analysis = result.analysis
    request = result.normalized_request

    typer.echo(f"Request       : {request.method} {request.path}")
    typer.echo(
        "Payload fields: "
        + ", ".join(request.body.keys())
    )
    typer.echo(f"Decision      : {analysis.decision}")

    if analysis.old_field is not None:
        typer.echo(f"Old field     : {analysis.old_field}")

    if analysis.new_field is not None:
        typer.echo(f"Required field: {analysis.new_field}")

    if analysis.score is not None:
        typer.echo(f"Score         : {analysis.score:.3f}")

    if analysis.confidence is not None:
        typer.echo(f"Confidence    : {analysis.confidence}")

    if not analysis.safe_to_patch:
        typer.echo("")
        typer.echo("Patch suggestion was not generated.")

        if analysis.reasons:
            typer.echo("")
            typer.echo("Reasons:")

            for reason in analysis.reasons:
                typer.echo(f"- {reason}")

        typer.echo("")
        typer.echo("No source files were changed.")

        raise typer.Exit(code=1)

    try:
        suggestion = build_python_patch_suggestion(
            result
        )
    except PythonDiffError as exc:
        typer.echo(
            f"Diff generation error: {exc}",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    typer.echo("")
    typer.echo("Suggested patch:")
    typer.echo("")
    typer.echo(
        suggestion.unified_diff.rstrip()
    )
    typer.echo("")
    typer.echo(
        f"Suggested rename: "
        f"{suggestion.old_field} -> "
        f"{suggestion.new_field}"
    )
    typer.echo("")
    typer.echo("No source files were changed.")


@pytest_app.command("batch")
def batch_pytest_requests(
    directory: Path = typer.Option(
        ...,
        "--directory",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Directory containing Python API test files.",
    ),
    openapi: Path = typer.Option(
        ...,
        "--openapi",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the OpenAPI contract file.",
    ),
    timeout: float = typer.Option(
        30,
        "--timeout",
        min=0.1,
        help="Maximum pytest validation time per patch.",
    ),
) -> None:
    """
    Scan, analyze, patch-plan and validate Python API tests.

    Suggested patches are validated using temporary files.
    Original source files are never modified.
    """

    typer.echo("")
    typer.echo("API Drift Healer - Pytest Batch")
    typer.echo("")
    typer.echo(f"Test directory: {directory}")
    typer.echo(f"OpenAPI       : {openapi}")
    typer.echo(f"Timeout       : {timeout:g} seconds")
    typer.echo("Mode          : SUGGEST_AND_VALIDATE")
    typer.echo("")

    try:
        validation_result = (
            validate_python_test_directory_patches(
                directory=directory,
                openapi_path=openapi,
                timeout_seconds=timeout,
            )
        )
    except (
        PytestNotAvailableError,
        PythonPatchValidationError,
    ) as exc:
        typer.echo(
            f"Validation error: {exc}",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    report = build_python_batch_report(
        validation_result
    )

    typer.echo(
        format_python_batch_report(report)
    )
    typer.echo("")
    typer.echo("No source files were changed.")

    if (
        report.pipeline_errors > 0
        or report.validation_failures > 0
    ):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()