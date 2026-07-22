import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from api_drift_healer.cli import app
from api_drift_healer.http_healer import (
    HttpHealError,
    HttpHealResult,
)
from api_drift_healer.models import DriftAnalysisResult


runner = CliRunner()


class HttpCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_directory.name)

        self.http_path = (
            self.base_path
            / "create-user.http"
        )

        self.openapi_path = (
            self.base_path
            / "openapi.yaml"
        )

        self.http_path.write_text(
            (
                "POST http://localhost:3000/users\n"
                "Content-Type: application/json\n"
                "\n"
                "{\n"
                '  "name": "Test User",\n'
                '  "userEmail": "qa_user@example.com"\n'
                "}\n"
            ),
            encoding="utf-8",
        )

        self.openapi_path.write_text(
            "openapi: 3.0.0\npaths: {}\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def make_result(
        self,
        *,
        decision: str = "SAFE_PATCH",
        output_path: Path | None = None,
        diff: str = (
            "--- create-user.http:before\n"
            "+++ create-user.http:after\n"
            '-  "userEmail": "qa_user@example.com"\n'
            '+  "email_address": "qa_user@example.com"\n'
        ),
    ) -> HttpHealResult:
        if decision in {"SAFE_PATCH", "REJECTED"}:
            old_field = "userEmail"
            new_field = "email_address"
            score = (
                0.772
                if decision == "SAFE_PATCH"
                else 0.158
            )
            threshold = 0.700
            confidence = (
                "High"
                if decision == "SAFE_PATCH"
                else "Low"
            )
        else:
            old_field = None
            new_field = None
            score = None
            threshold = None
            confidence = None

        analysis = DriftAnalysisResult(
            decision=decision,
            request_name="create-user",
            missing_required_fields=(
                ("email_address",)
                if decision != "NO_DRIFT"
                else ()
            ),
            invalid_existing_fields=(
                ("userEmail",)
                if decision != "NO_DRIFT"
                else ()
            ),
            old_field=old_field,
            new_field=new_field,
            score=score,
            threshold=threshold,
            confidence=confidence,
            reasons=(
                ("Automatic patch was rejected.",)
                if decision == "REJECTED"
                else ()
            ),
        )

        before_source = self.http_path.read_text(
            encoding="utf-8"
        )

        after_source = before_source.replace(
            '"userEmail"',
            '"email_address"',
            1,
        )

        return HttpHealResult(
            analysis=analysis,
            source_path=self.http_path.resolve(),
            output_path=output_path,
            before_source=before_source,
            after_source=after_source,
            diff=diff if decision == "SAFE_PATCH" else "",
        )

    def test_main_help_lists_http_command(self) -> None:
        result = runner.invoke(
            app,
            ["--help"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("http", result.output)

    def test_http_help_lists_heal_command(self) -> None:
        result = runner.invoke(
            app,
            ["http", "--help"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("heal", result.output)

    def test_http_heal_requires_file_option(self) -> None:
        result = runner.invoke(
            app,
            [
                "http",
                "heal",
                "--openapi",
                str(self.openapi_path),
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--file", result.output)

    def test_http_heal_requires_openapi_option(self) -> None:
        result = runner.invoke(
            app,
            [
                "http",
                "heal",
                "--file",
                str(self.http_path),
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--openapi", result.output)

    @patch(
        "api_drift_healer.cli.heal_http_file"
    )
    def test_dry_run_calls_service_and_prints_diff(
        self,
        mock_heal,
    ) -> None:
        mock_heal.return_value = self.make_result()

        result = runner.invoke(
            app,
            [
                "http",
                "heal",
                "--file",
                str(self.http_path),
                "--openapi",
                str(self.openapi_path),
                "--dry-run",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            "API Drift Healer V1.1 HTTP File CLI",
            result.output,
        )
        self.assertIn(
            "Mode: DRY RUN",
            result.output,
        )
        self.assertIn(
            "Decision: SAFE_PATCH",
            result.output,
        )
        self.assertIn(
            "userEmail",
            result.output,
        )
        self.assertIn(
            "email_address",
            result.output,
        )
        self.assertIn(
            "No HTTP file was written",
            result.output,
        )

        call_args = mock_heal.call_args.kwargs

        self.assertEqual(
            Path(
                call_args["file_path"]
            ).resolve(),
            self.http_path.resolve(),
        )

        self.assertEqual(
            Path(
                call_args["openapi_path"]
            ).resolve(),
            self.openapi_path.resolve(),
        )

        self.assertTrue(call_args["dry_run"])
        self.assertFalse(call_args["overwrite"])

    @patch(
        "api_drift_healer.cli.heal_http_file"
    )
    def test_safe_write_prints_output_path(
        self,
        mock_heal,
    ) -> None:
        output_path = (
            self.base_path
            / "create-user.healed.http"
        ).resolve()

        mock_heal.return_value = self.make_result(
            output_path=output_path,
        )

        result = runner.invoke(
            app,
            [
                "http",
                "heal",
                "--file",
                str(self.http_path),
                "--openapi",
                str(self.openapi_path),
                "--output",
                str(output_path),
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            "Healed HTTP file generated",
            result.output,
        )
        self.assertIn(
            str(output_path),
            result.output,
        )

    @patch(
        "api_drift_healer.cli.heal_http_file"
    )
    def test_no_drift_returns_success(
        self,
        mock_heal,
    ) -> None:
        mock_heal.return_value = self.make_result(
            decision="NO_DRIFT",
        )

        result = runner.invoke(
            app,
            [
                "http",
                "heal",
                "--file",
                str(self.http_path),
                "--openapi",
                str(self.openapi_path),
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            "Decision: NO_DRIFT",
            result.output,
        )

    @patch(
        "api_drift_healer.cli.heal_http_file"
    )
    def test_rejected_patch_returns_failure(
        self,
        mock_heal,
    ) -> None:
        mock_heal.return_value = self.make_result(
            decision="REJECTED",
        )

        result = runner.invoke(
            app,
            [
                "http",
                "heal",
                "--file",
                str(self.http_path),
                "--openapi",
                str(self.openapi_path),
            ],
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn(
            "Decision: REJECTED",
            result.output,
        )
        self.assertIn(
            "was not applied",
            result.output,
        )

    @patch(
        "api_drift_healer.cli.heal_http_file",
        side_effect=HttpHealError(
            "Test HTTP healing error."
        ),
    )
    def test_service_error_returns_invalid_input_code(
        self,
        mock_heal,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "http",
                "heal",
                "--file",
                str(self.http_path),
                "--openapi",
                str(self.openapi_path),
            ],
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn(
            "[ERROR]",
            result.output,
        )
        self.assertIn(
            "Test HTTP healing error",
            result.output,
        )

        mock_heal.assert_called_once()


if __name__ == "__main__":
    unittest.main()