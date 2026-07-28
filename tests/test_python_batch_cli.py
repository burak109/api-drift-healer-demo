import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from api_drift_healer.cli import app
from api_drift_healer.python_patch_validator import (
    PytestNotAvailableError,
)


class PythonBatchCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_pytest_help_lists_batch_command(self) -> None:
        result = self.runner.invoke(
            app,
            [
                "pytest",
                "--help",
            ],
        )

        self.assertEqual(
            result.exit_code,
            0,
            result.output,
        )
        self.assertIn(
            "batch",
            result.output,
        )

    @patch(
        "api_drift_healer.cli."
        "format_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "build_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "validate_python_test_directory_patches",
        create=True,
    )
    def test_batch_prints_aggregate_report(
        self,
        validate_mock,
        build_report_mock,
        format_report_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tests_directory = root / "tests"
            tests_directory.mkdir()

            openapi_path = root / "openapi.json"
            openapi_path.write_text(
                "{}",
                encoding="utf-8",
            )

            validation_result = SimpleNamespace()
            report = SimpleNamespace(
                pipeline_errors=0,
                validation_failures=0,
            )

            validate_mock.return_value = validation_result
            build_report_mock.return_value = report
            format_report_mock.return_value = (
                "Python Batch Report\n"
                "Files scanned: 3\n"
                "Requests analyzed: 4\n"
                "Patches validated: 1"
            )

            result = self.runner.invoke(
                app,
                [
                    "pytest",
                    "batch",
                    "--directory",
                    str(tests_directory),
                    "--openapi",
                    str(openapi_path),
                    "--timeout",
                    "12",
                ],
            )

            self.assertEqual(
                result.exit_code,
                0,
                result.output,
            )
            self.assertIn(
                "API Drift Healer - Pytest Batch",
                result.output,
            )
            self.assertIn(
                "Files scanned: 3",
                result.output,
            )
            self.assertIn(
                "Patches validated: 1",
                result.output,
            )
            self.assertIn(
                "No source files were changed.",
                result.output,
            )

            validate_mock.assert_called_once_with(
                directory=tests_directory.resolve(),
                openapi_path=openapi_path.resolve(),
                timeout_seconds=12,
            )
            build_report_mock.assert_called_once_with(
                validation_result
            )
            format_report_mock.assert_called_once_with(
                report
            )

    @patch(
        "api_drift_healer.cli."
        "format_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "build_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "validate_python_test_directory_patches",
        create=True,
    )
    def test_batch_writes_report_file(
        self,
        validate_mock,
        build_report_mock,
        format_report_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            tests_directory = root / "tests"
            tests_directory.mkdir()

            openapi_path = root / "openapi.json"
            openapi_path.write_text(
                "{}",
                encoding="utf-8",
            )

            report_path = (
                root
                / "artifacts"
                / "api-drift-report.md"
            )

            validation_result = SimpleNamespace()
            report = SimpleNamespace(
                pipeline_errors=0,
                validation_failures=0,
            )
            formatted_report = (
                "Python Batch Report\n"
                "Files scanned: 3\n"
                "Requests analyzed: 4\n"
                "Patches validated: 1"
            )

            validate_mock.return_value = validation_result
            build_report_mock.return_value = report
            format_report_mock.return_value = (
                formatted_report
            )

            result = self.runner.invoke(
                app,
                [
                    "pytest",
                    "batch",
                    "--directory",
                    str(tests_directory),
                    "--openapi",
                    str(openapi_path),
                    "--report-file",
                    str(report_path),
                ],
            )

            self.assertEqual(
                result.exit_code,
                0,
                result.output,
            )
            self.assertTrue(report_path.is_file())
            self.assertEqual(
                report_path.read_text(
                    encoding="utf-8"
                ),
                (
                    formatted_report
                    + "\n\n"
                    + "No source files were changed.\n"
                ),
            )
            self.assertIn(
                f"Report written: {report_path}",
                result.output,
            )

    @patch(
        "api_drift_healer.cli."
        "format_python_batch_report_markdown",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "format_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "build_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "validate_python_test_directory_patches",
        create=True,
    )
    def test_batch_writes_markdown_report(
        self,
        validate_mock,
        build_report_mock,
        format_report_mock,
        format_markdown_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            tests_directory = root / "tests"
            tests_directory.mkdir()

            openapi_path = root / "openapi.json"
            openapi_path.write_text(
                "{}",
                encoding="utf-8",
            )

            markdown_path = (
                root
                / "artifacts"
                / "api-drift-report.md"
            )

            validation_result = SimpleNamespace()
            report = SimpleNamespace(
                pipeline_errors=0,
                validation_failures=0,
            )
            markdown_report = (
                "# API Drift Healer Batch Report\n\n"
                "| Metric | Value |"
            )

            validate_mock.return_value = validation_result
            build_report_mock.return_value = report
            format_report_mock.return_value = (
                "Python Batch Report"
            )
            format_markdown_mock.return_value = (
                markdown_report
            )

            result = self.runner.invoke(
                app,
                [
                    "pytest",
                    "batch",
                    "--directory",
                    str(tests_directory),
                    "--openapi",
                    str(openapi_path),
                    "--report-markdown",
                    str(markdown_path),
                ],
            )

            self.assertEqual(
                result.exit_code,
                0,
                result.output,
            )
            self.assertTrue(markdown_path.is_file())
            self.assertEqual(
                markdown_path.read_text(
                    encoding="utf-8"
                ),
                markdown_report + "\n",
            )
            self.assertIn(
                (
                    "Markdown report written: "
                    f"{markdown_path}"
                ),
                result.output,
            )

            format_markdown_mock.assert_called_once_with(
                report
            )

    @patch(
        "api_drift_healer.cli."
        "format_python_batch_report_json",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "format_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "build_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "validate_python_test_directory_patches",
        create=True,
    )
    def test_batch_writes_json_report(
        self,
        validate_mock,
        build_report_mock,
        format_report_mock,
        format_json_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            tests_directory = root / "tests"
            tests_directory.mkdir()

            openapi_path = root / "openapi.json"
            openapi_path.write_text(
                "{}",
                encoding="utf-8",
            )

            json_path = (
                root
                / "artifacts"
                / "api-drift-report.json"
            )

            validation_result = SimpleNamespace()
            report = SimpleNamespace(
                pipeline_errors=0,
                validation_failures=0,
            )

            validate_mock.return_value = validation_result
            build_report_mock.return_value = report
            format_report_mock.return_value = (
                "Python Batch Report"
            )
            format_json_mock.return_value = (
                '{"schema_version": 1, '
                '"source_files_changed": false}'
            )

            result = self.runner.invoke(
                app,
                [
                    "pytest",
                    "batch",
                    "--directory",
                    str(tests_directory),
                    "--openapi",
                    str(openapi_path),
                    "--report-json",
                    str(json_path),
                ],
            )

            self.assertEqual(
                result.exit_code,
                0,
                result.output,
            )
            self.assertTrue(json_path.is_file())

            payload = json.loads(
                json_path.read_text(encoding="utf-8")
            )
            self.assertEqual(payload["schema_version"], 1)
            self.assertFalse(
                payload["source_files_changed"]
            )

            self.assertIn(
                f"JSON report written: {json_path}",
                result.output,
            )

            format_json_mock.assert_called_once_with(
                report
            )

    @patch(
        "api_drift_healer.cli."
        "format_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "build_python_batch_report",
        create=True,
    )
    @patch(
        "api_drift_healer.cli."
        "validate_python_test_directory_patches",
        create=True,
    )
    def test_batch_returns_failure_for_validation_failures(
        self,
        validate_mock,
        build_report_mock,
        format_report_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tests_directory = root / "tests"
            tests_directory.mkdir()

            openapi_path = root / "openapi.json"
            openapi_path.write_text(
                "{}",
                encoding="utf-8",
            )

            validate_mock.return_value = SimpleNamespace()
            build_report_mock.return_value = SimpleNamespace(
                pipeline_errors=0,
                validation_failures=1,
            )
            format_report_mock.return_value = (
                "Validation failures: 1"
            )

            result = self.runner.invoke(
                app,
                [
                    "pytest",
                    "batch",
                    "--directory",
                    str(tests_directory),
                    "--openapi",
                    str(openapi_path),
                ],
            )

            self.assertEqual(
                result.exit_code,
                1,
                result.output,
            )
            self.assertIn(
                "Validation failures: 1",
                result.output,
            )

    @patch(
        "api_drift_healer.cli."
        "validate_python_test_directory_patches",
        create=True,
    )
    def test_batch_reports_missing_pytest(
        self,
        validate_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tests_directory = root / "tests"
            tests_directory.mkdir()

            openapi_path = root / "openapi.json"
            openapi_path.write_text(
                "{}",
                encoding="utf-8",
            )

            validate_mock.side_effect = (
                PytestNotAvailableError(
                    "pytest is not installed"
                )
            )

            result = self.runner.invoke(
                app,
                [
                    "pytest",
                    "batch",
                    "--directory",
                    str(tests_directory),
                    "--openapi",
                    str(openapi_path),
                ],
            )

            self.assertEqual(
                result.exit_code,
                1,
                result.output,
            )
            self.assertIn(
                "pytest is not installed",
                result.output,
            )


if __name__ == "__main__":
    unittest.main()
