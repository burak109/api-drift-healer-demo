from pathlib import Path
from typing import Optional

import typer

from api_drift_healer.adapters.postman import PostmanAdapterError
from api_drift_healer.drift_analyzer import DriftAnalyzerError
from api_drift_healer.openapi_resolver import OpenApiResolverError
from api_drift_healer.postman_healer import (
    PostmanHealError,
    heal_postman_collection,
)
from auto_healer import run_healer


app = typer.Typer(
    name="api-drift-healer",
    help=(
        "Detect and safely heal API contract drift "
        "in YAML tests and Postman collections."
    ),
    no_args_is_help=True,
)

postman_app = typer.Typer(
    help="Auto-heal Postman collections from OpenAPI drift.",
    no_args_is_help=True,
)

app.add_typer(
    postman_app,
    name="postman",
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

    typer.echo("API Drift Healer V0.6 CLI")
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
) -> None:
    """Auto-heal one Postman request from OpenAPI drift."""

    mode = "DRY RUN" if dry_run else "HEAL"

    typer.echo("API Drift Healer V1 Postman CLI")
    typer.echo(f"Collection: {collection}")
    typer.echo(f"Request: {request_name}")
    typer.echo(f"OpenAPI: {openapi}")

    if output is not None:
        typer.echo(f"Output: {output}")

    typer.echo(f"Mode: {mode}")
    typer.echo("")

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
                "No collection file was written."
            )
        elif result.output_path is not None:
            typer.echo("")
            typer.echo(
                f"[+] Healed collection generated: "
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


if __name__ == "__main__":
    app()
