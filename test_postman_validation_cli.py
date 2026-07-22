import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from api_drift_healer.cli import app
from api_drift_healer.newman_runner import (
    NewmanRunResult,
    NewmanRunnerError,
)


PROJECT_ROOT = Path(__file__).resolve().parent

EXAMPLE_COLLECTION = (
    PROJECT_ROOT
    / "examples"
    / "postman"
    / "create-user.postman_collection.json"
)

EXAMPLE_OPENAPI = (
    PROJECT_ROOT
    / "examples"
    / "postman"
    / "openapi.yaml"
)

runner = CliRunner()


def base_arguments() -> list[str]:
    """Return the required Postman CLI arguments."""

    return [
        "postman",
        "heal",
        "--collection",
        str(EXAMPLE_COLLECTION),
        "--request",
        "Create User",
        "--openapi",
        str(EXAMPLE_OPENAPI),
    ]


def make_analysis(
    decision: str = "SAFE_PATCH",
):
    """Create a minimal drift-analysis result for CLI tests."""

    return SimpleNamespace(
        decision=decision,
        old_field=(
            "userEmail"
            if decision == "SAFE_PATCH"
            else None
        ),
        new_field=(
            "email_address"
            if decision == "SAFE_PATCH"
            else None
        ),
        score=(
            0.772
            if decision == "SAFE_PATCH"
            else None
        ),
        threshold=(
            0.700
            if decision == "SAFE_PATCH"
            else None
        ),
        confidence=(
            "High"
            if decision == "SAFE_PATCH"
            else None
        ),
        reasons=(
            "Automatic patch was rejected.",
        ),
    )


def make_newman_result(
    return_code: int,
    *,
    stdout: str = "",
) -> NewmanRunResult:
    """Create one fake Newman execution result."""

    return NewmanRunResult(
        collection_path=EXAMPLE_COLLECTION.resolve(),
        environment_path=None,
        command=(
            "newman",
            "run",
            str(EXAMPLE_COLLECTION.resolve()),
        ),
        return_code=return_code,
        stdout=stdout,
        stderr="",
    )


def make_validation_result(
    decision: str,
    *,
    output_path: Path | None = None,
    original_return_code: int | None = None,
    healed_return_code: int | None = None,
    healed_stdout: str = "",
):
    """Create a minimal validation result for CLI tests."""

    original_run = (
        make_newman_result(
            original_return_code,
            stdout="Original Newman result.",
        )
        if original_return_code is not None
        else None
    )

    healed_run = (
        make_newman_result(
            healed_return_code,
            stdout=healed_stdout,
        )
        if healed_return_code is not None
        else None
    )

    return SimpleNamespace(
        decision=decision,
        heal_result=SimpleNamespace(
            analysis=make_analysis(),
            diff=(
                "--- original\n"
                "+++ healed\n"
                "- userEmail\n"
                "+ email_address\n"
            ),
        ),
        original_run=original_run,
        healed_run=healed_run,
        output_path=output_path,
    )


class PostmanValidationCliTests(unittest.TestCase):
    def test_help_lists_newman_options(self) -> None:
        result = runner.invoke(
            app,
            [
                "postman",
                "heal",
                "--help",
            ],
        )

        self.assertEqual(
            result.exit_code,
            0,
            msg=result.output,
        )

        self.assertIn(
            "--validate-newman",
            result.output,
        )
        self.assertIn(
            "--environment",
            result.output,
        )
        self.assertIn(
            "--newman-timeout",
            result.output,
        )
        self.assertIn(
            "--allow-original-pass",
            result.output,
        )

    def test_dry_run_cannot_be_combined_with_validation(
        self,
    ) -> None:
        result = runner.invoke(
            app,
            base_arguments()
            + [
                "--dry-run",
                "--validate-newman",
            ],
        )

        self.assertEqual(
            result.exit_code,
            2,
            msg=result.output,
        )

        self.assertIn(
            "--dry-run cannot be used together with "
            "--validate-newman",
            result.output,
        )

    def test_environment_requires_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment_path = (
                Path(directory)
                / "demo.postman_environment.json"
            )

            environment_path.write_text(
                "{}",
                encoding="utf-8",
            )

            result = runner.invoke(
                app,
                base_arguments()
                + [
                    "--environment",
                    str(environment_path),
                ],
            )

        self.assertEqual(
            result.exit_code,
            2,
            msg=result.output,
        )

        self.assertIn(
            "--environment requires --validate-newman",
            result.output,
        )

    def test_allow_original_pass_requires_validation(
        self,
    ) -> None:
        result = runner.invoke(
            app,
            base_arguments()
            + [
                "--allow-original-pass",
            ],
        )

        self.assertEqual(
            result.exit_code,
            2,
            msg=result.output,
        )

        self.assertIn(
            "--allow-original-pass requires "
            "--validate-newman",
            result.output,
        )

    def test_validated_result_returns_success(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "validated.postman_collection.json"
            )

            validation_result = make_validation_result(
                "VALIDATED",
                output_path=output_path.resolve(),
                original_return_code=1,
                healed_return_code=0,
            )

            with patch(
                "api_drift_healer.cli."
                "validate_postman_heal",
                return_value=validation_result,
            ):
                result = runner.invoke(
                    app,
                    base_arguments()
                    + [
                        "--validate-newman",
                        "--output",
                        str(output_path),
                    ],
                )

        self.assertEqual(
            result.exit_code,
            0,
            msg=result.output,
        )

        self.assertIn(
            "Static analysis: SAFE_PATCH",
            result.output,
        )
        self.assertIn(
            "Original Newman: FAIL (exit code 1)",
            result.output,
        )
        self.assertIn(
            "Healed Newman: PASS",
            result.output,
        )
        self.assertIn(
            "Decision: VALIDATED",
            result.output,
        )
        self.assertIn(
            "Validated Postman collection generated",
            result.output,
        )

    def test_original_pass_returns_failure_without_output(
        self,
    ) -> None:
        validation_result = make_validation_result(
            "ORIGINAL_PASSED",
            original_return_code=0,
        )

        with patch(
            "api_drift_healer.cli."
            "validate_postman_heal",
            return_value=validation_result,
        ):
            result = runner.invoke(
                app,
                base_arguments()
                + [
                    "--validate-newman",
                ],
            )

        self.assertEqual(
            result.exit_code,
            1,
            msg=result.output,
        )

        self.assertIn(
            "Original Newman: PASS",
            result.output,
        )
        self.assertIn(
            "Decision: ORIGINAL_PASSED",
            result.output,
        )
        self.assertIn(
            "Validated output was not written",
            result.output,
        )
        self.assertIn(
            "--allow-original-pass",
            result.output,
        )

    def test_healed_failure_returns_failure(
        self,
    ) -> None:
        validation_result = make_validation_result(
            "HEALED_FAILED",
            original_return_code=1,
            healed_return_code=1,
            healed_stdout="1 assertion failed.",
        )

        with patch(
            "api_drift_healer.cli."
            "validate_postman_heal",
            return_value=validation_result,
        ):
            result = runner.invoke(
                app,
                base_arguments()
                + [
                    "--validate-newman",
                ],
            )

        self.assertEqual(
            result.exit_code,
            1,
            msg=result.output,
        )

        self.assertIn(
            "Healed Newman: FAIL (exit code 1)",
            result.output,
        )
        self.assertIn(
            "Decision: HEALED_FAILED",
            result.output,
        )
        self.assertIn(
            "Validated output was not written",
            result.output,
        )
        self.assertIn(
            "1 assertion failed.",
            result.output,
        )

    def test_newman_runner_error_returns_tooling_error(
        self,
    ) -> None:
        with patch(
            "api_drift_healer.cli."
            "validate_postman_heal",
            side_effect=NewmanRunnerError(
                "Newman executable was not found."
            ),
        ):
            result = runner.invoke(
                app,
                base_arguments()
                + [
                    "--validate-newman",
                ],
            )

        self.assertEqual(
            result.exit_code,
            2,
            msg=result.output,
        )

        self.assertIn(
            "[ERROR] Newman executable was not found.",
            result.output,
        )

    def test_validation_options_are_forwarded(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_path = Path(directory)

            environment_path = (
                temp_path
                / "demo.postman_environment.json"
            )

            environment_path.write_text(
                "{}",
                encoding="utf-8",
            )

            output_path = (
                temp_path
                / "validated.postman_collection.json"
            )

            validation_result = make_validation_result(
                "VALIDATED",
                output_path=output_path.resolve(),
                original_return_code=0,
                healed_return_code=0,
            )

            with patch(
                "api_drift_healer.cli."
                "validate_postman_heal",
                return_value=validation_result,
            ) as validate_mock:
                result = runner.invoke(
                    app,
                    base_arguments()
                    + [
                        "--validate-newman",
                        "--environment",
                        str(environment_path),
                        "--output",
                        str(output_path),
                        "--overwrite",
                        "--newman-timeout",
                        "45",
                        "--allow-original-pass",
                    ],
                )

            self.assertEqual(
                result.exit_code,
                0,
                msg=result.output,
            )

            validate_mock.assert_called_once()

            call_kwargs = (
                validate_mock.call_args.kwargs
            )

            self.assertEqual(
                call_kwargs["collection_path"],
                EXAMPLE_COLLECTION.resolve(),
            )
            self.assertEqual(
                call_kwargs["openapi_path"],
                EXAMPLE_OPENAPI.resolve(),
            )
            self.assertEqual(
                call_kwargs["request_name"],
                "Create User",
            )
            self.assertEqual(
                call_kwargs["environment_path"],
                environment_path.resolve(),
            )
            self.assertEqual(
                call_kwargs["output_path"],
                output_path,
            )
            self.assertTrue(
                call_kwargs["overwrite"]
            )
            self.assertEqual(
                call_kwargs["timeout_seconds"],
                45.0,
            )
            self.assertFalse(
                call_kwargs["require_original_failure"]
            )


if __name__ == "__main__":
    unittest.main()