from pathlib import Path
from typing import Optional

import typer

from auto_healer import run_healer


app = typer.Typer(
    name="api-drift-healer",
    help="Detect and safely heal API contract drift in YAML test cases.",
    no_args_is_help=True,
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
    """Analyze and heal API contract drift."""

    if dry_run and apply_patch:
        raise typer.BadParameter(
            "--dry-run cannot be used together with --apply."
        )

    if create_pr and not apply_patch:
        raise typer.BadParameter(
            "--create-pr requires --apply."
        )

    resolved_output = output or test.with_name(
        f"{test.stem}.healed{test.suffix}"
    )

    if apply_patch:
        raise typer.BadParameter(
            "--apply behavior will be implemented in the next V0.5 step."
        )

    report_file = resolved_output.with_name("heal_report.md")

    typer.echo("API Drift Healer V0.5 CLI")
    typer.echo(f"Test file: {test}")
    typer.echo(f"OpenAPI file: {openapi}")
    typer.echo(f"Output file: {resolved_output}")
    typer.echo("")

    exit_code = run_healer(
        test_case_file=test,
        openapi_file=openapi,
        healed_test_file=resolved_output,
        report_file=report_file,
        create_pr=False,
        dry_run=dry_run,
    )

    raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    app()