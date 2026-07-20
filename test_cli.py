import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from api_drift_healer.cli import app


runner = CliRunner()


class ApiDriftHealerCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        self.test_file = self.base_path / "api_test_case.yaml"
        self.openapi_file = self.base_path / "openapi.yaml"

        self.test_file.write_text(
            """
name: Create User - Success
method: POST
url: http://localhost:3000/users
expected_status: 201
body:
  name: Test User
  userEmail: qa_user@example.com
""".strip(),
            encoding="utf-8",
        )

        self.openapi_file.write_text(
            """
openapi: 3.0.0
paths: {}
""".strip(),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_main_help_lists_heal_command(self):
        result = runner.invoke(app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("heal", result.output)
        self.assertIn(
            "Detect and safely heal API contract drift",
            result.output,
        )

    def test_heal_requires_test_and_openapi_options(self):
        missing_test_result = runner.invoke(
            app,
            ["heal"],
        )

        self.assertNotEqual(
            missing_test_result.exit_code,
            0,
        )
        self.assertIn(
            "--test",
            missing_test_result.output,
        )

        missing_openapi_result = runner.invoke(
            app,
            [
                "heal",
                "--test",
                str(self.test_file),
            ],
        )

        self.assertNotEqual(
            missing_openapi_result.exit_code,
            0,
        )
        self.assertIn(
            "--openapi",
            missing_openapi_result.output,
        )

    def test_dry_run_and_apply_cannot_be_combined(self):
        result = runner.invoke(
            app,
            [
                "heal",
                "--test",
                str(self.test_file),
                "--openapi",
                str(self.openapi_file),
                "--dry-run",
                "--apply",
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "--dry-run cannot be used together with --apply",
            result.output,
        )

    def test_create_pr_requires_apply(self):
        result = runner.invoke(
            app,
            [
                "heal",
                "--test",
                str(self.test_file),
                "--openapi",
                str(self.openapi_file),
                "--create-pr",
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "--create-pr requires --apply",
            result.output,
        )

    @patch("api_drift_healer.cli.run_healer", return_value=0)
    def test_default_heal_mode_calls_engine(
        self,
        mock_run_healer,
    ):
        result = runner.invoke(
            app,
            [
                "heal",
                "--test",
                str(self.test_file),
                "--openapi",
                str(self.openapi_file),
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Mode: HEAL", result.output)

        mock_run_healer.assert_called_once()

        call_args = mock_run_healer.call_args.kwargs

        resolved_test = self.test_file.resolve()
        resolved_openapi = self.openapi_file.resolve()
        expected_output = resolved_test.with_name(
            "api_test_case.healed.yaml"
        )
        expected_report = expected_output.with_name(
            "heal_report.md"
        )

        self.assertEqual(
            Path(call_args["test_case_file"]).resolve(),
            resolved_test,
        )
        self.assertEqual(
            Path(call_args["openapi_file"]).resolve(),
            resolved_openapi,
        )
        self.assertEqual(
            Path(call_args["healed_test_file"]).resolve(),
            expected_output,
        )
        self.assertEqual(
            Path(call_args["report_file"]).resolve(),
            expected_report,
        )

        self.assertFalse(call_args["create_pr"])
        self.assertFalse(call_args["dry_run"])
        self.assertFalse(call_args["apply_patch"])

    @patch("api_drift_healer.cli.run_healer", return_value=0)
    def test_dry_run_mode_calls_engine_without_apply(
        self,
        mock_run_healer,
    ):
        result = runner.invoke(
            app,
            [
                "heal",
                "--test",
                str(self.test_file),
                "--openapi",
                str(self.openapi_file),
                "--dry-run",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Mode: DRY RUN", result.output)

        call_args = mock_run_healer.call_args.kwargs

        self.assertTrue(call_args["dry_run"])
        self.assertFalse(call_args["apply_patch"])
        self.assertFalse(call_args["create_pr"])

    @patch("api_drift_healer.cli.run_healer", return_value=0)
    def test_apply_mode_calls_engine_with_apply_enabled(
        self,
        mock_run_healer,
    ):
        result = runner.invoke(
            app,
            [
                "heal",
                "--test",
                str(self.test_file),
                "--openapi",
                str(self.openapi_file),
                "--apply",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Mode: APPLY", result.output)

        call_args = mock_run_healer.call_args.kwargs

        self.assertFalse(call_args["dry_run"])
        self.assertTrue(call_args["apply_patch"])
        self.assertFalse(call_args["create_pr"])

    @patch("api_drift_healer.cli.run_healer", return_value=0)
    def test_custom_output_is_forwarded_to_engine(
        self,
        mock_run_healer,
    ):
        custom_output = (
            self.base_path
            / "generated"
            / "healed.yaml"
        )

        result = runner.invoke(
            app,
            [
                "heal",
                "--test",
                str(self.test_file),
                "--openapi",
                str(self.openapi_file),
                "--output",
                str(custom_output),
            ],
        )

        self.assertEqual(result.exit_code, 0)

        call_args = mock_run_healer.call_args.kwargs

        self.assertEqual(
            Path(
                call_args["healed_test_file"]
            ).resolve(),
            custom_output.resolve(),
        )
        self.assertEqual(
            Path(
                call_args["report_file"]
            ).resolve(),
            custom_output.with_name(
                "heal_report.md"
            ).resolve(),
        )


if __name__ == "__main__":
    unittest.main()