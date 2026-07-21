import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from api_drift_healer.cli import app
from api_drift_healer.models import DriftAnalysisResult
from api_drift_healer.postman_healer import (
    PostmanHealError,
    PostmanHealResult,
)


runner = CliRunner()


class PostmanCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_directory.name)

        self.collection_path = (
            self.base_path
            / "demo.postman_collection.json"
        )

        self.openapi_path = (
            self.base_path
            / "openapi.yaml"
        )

        self.collection_path.write_text(
            "{}",
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
            "--- Create User:before\n"
            "+++ Create User:after\n"
            '-  "userEmail": "qa_user@example.com"\n'
            '+  "email_address": "qa_user@example.com"\n'
        ),
    ) -> PostmanHealResult:
        if decision in {"SAFE_PATCH", "REJECTED"}:
            old_field = "userEmail"
            new_field = "email_address"
            score = 0.772 if decision == "SAFE_PATCH" else 0.158
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
            request_name="Create User",
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
                "Decision generated for CLI testing.",
            ),
        )

        before_body = {
            "name": "Test User",
            "userEmail": "qa_user@example.com",
        }

        after_body = (
            {
                "name": "Test User",
                "email_address": "qa_user@example.com",
            }
            if decision == "SAFE_PATCH"
            else before_body
        )

        return PostmanHealResult(
            analysis=analysis,
            source_path=self.collection_path.resolve(),
            output_path=output_path,
            before_body=before_body,
            after_body=after_body,
            diff=(
                diff
                if decision == "SAFE_PATCH"
                else ""
            ),
        )

    def test_main_help_lists_postman_command(self) -> None:
        result = runner.invoke(
            app,
            ["--help"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("postman", result.output)
        self.assertIn("heal", result.output)

    def test_postman_help_lists_heal_command(self) -> None:
        result = runner.invoke(
            app,
            ["postman", "--help"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("heal", result.output)
        self.assertIn(
            "Postman",
            result.output,
        )

    def test_postman_heal_requires_options(self) -> None:
        missing_collection_result = runner.invoke(
            app,
            [
                "postman",
                "heal",
                "--request",
                "Create User",
                "--openapi",
                str(self.openapi_path),
            ],
        )

        self.assertNotEqual(
            missing_collection_result.exit_code,
            0,
        )
        self.assertIn(
            "--collection",
            missing_collection_result.output,
        )

        missing_request_result = runner.invoke(
            app,
            [
                "postman",
                "heal",
                "--collection",
                str(self.collection_path),
                "--openapi",
                str(self.openapi_path),
            ],
        )

        self.assertNotEqual(
            missing_request_result.exit_code,
            0,
        )
        self.assertIn(
            "--request",
            missing_request_result.output,
        )

        missing_openapi_result = runner.invoke(
            app,
            [
                "postman",
                "heal",
                "--collection",
                str(self.collection_path),
                "--request",
                "Create User",
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

    @patch(
        "api_drift_healer.cli.heal_postman_collection"
    )
    def test_dry_run_calls_service_and_prints_diff(
        self,
        mock_heal,
    ) -> None:
        mock_heal.return_value = self.make_result()

        result = runner.invoke(
            app,
            [
                "postman",
                "heal",
                "--collection",
                str(self.collection_path),
                "--request",
                "Create User",
                "--openapi",
                str(self.openapi_path),
                "--dry-run",
            ],
        )

        self.assertEqual(result.exit_code, 0)
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

        call_args = mock_heal.call_args.kwargs

        self.assertEqual(
            Path(
                call_args["collection_path"]
            ).resolve(),
            self.collection_path.resolve(),
        )

        self.assertEqual(
            Path(
                call_args["openapi_path"]
            ).resolve(),
            self.openapi_path.resolve(),
        )

        self.assertEqual(
            call_args["request_name"],
            "Create User",
        )

        self.assertTrue(
            call_args["dry_run"]
        )
        self.assertFalse(
            call_args["overwrite"]
        )

    @patch(
        "api_drift_healer.cli.heal_postman_collection"
    )
    def test_safe_write_prints_output_path(
        self,
        mock_heal,
    ) -> None:
        output_path = (
            self.base_path
            / "healed.postman_collection.json"
        ).resolve()

        mock_heal.return_value = self.make_result(
            output_path=output_path,
        )

        result = runner.invoke(
            app,
            [
                "postman",
                "heal",
                "--collection",
                str(self.collection_path),
                "--request",
                "Create User",
                "--openapi",
                str(self.openapi_path),
                "--output",
                str(output_path),
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            "Healed collection generated",
            result.output,
        )
        self.assertIn(
            str(output_path),
            result.output,
        )

    @patch(
        "api_drift_healer.cli.heal_postman_collection"
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
                "postman",
                "heal",
                "--collection",
                str(self.collection_path),
                "--request",
                "Create User",
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
        "api_drift_healer.cli.heal_postman_collection"
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
                "postman",
                "heal",
                "--collection",
                str(self.collection_path),
                "--request",
                "Create User",
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
        "api_drift_healer.cli.heal_postman_collection",
        side_effect=PostmanHealError(
            "Test Postman healing error."
        ),
    )
    def test_service_error_returns_invalid_input_code(
        self,
        mock_heal,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "postman",
                "heal",
                "--collection",
                str(self.collection_path),
                "--request",
                "Create User",
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
            "Test Postman healing error",
            result.output,
        )

        mock_heal.assert_called_once()


if __name__ == "__main__":
    unittest.main()
