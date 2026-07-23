import json
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from typer.testing import CliRunner

from api_drift_healer.cli import app


class PythonCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_pytest_help_lists_analyze_command(self) -> None:
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
            "analyze",
            result.output,
        )
        self.assertIn(
            "Detect stale payload fields",
            result.output,
        )

    def test_safe_patch_prints_diff_without_changing_file(
        self,
    ) -> None:
        python_source = dedent(
            '''
            import requests

            payload = {
                "name": "Test User",
                "userEmail": "qa_user@example.com",
            }

            requests.post(
                "http://localhost:3000/users",
                json=payload,
            )
            '''
        ).lstrip()

        with tempfile.TemporaryDirectory() as directory:
            python_path, openapi_path = self._write_files(
                directory=directory,
                python_source=python_source,
            )

            result = self.runner.invoke(
                app,
                [
                    "pytest",
                    "analyze",
                    "--file",
                    str(python_path),
                    "--openapi",
                    str(openapi_path),
                ],
            )

            self.assertEqual(
                result.exit_code,
                0,
                result.output,
            )
            self.assertIn(
                "Request       : POST /users",
                result.output,
            )
            self.assertIn(
                "Decision      : SAFE_PATCH",
                result.output,
            )
            self.assertIn(
                "userEmail -> email_address",
                result.output,
            )
            self.assertIn(
                '-    "userEmail":',
                result.output,
            )
            self.assertIn(
                '+    "email_address":',
                result.output,
            )
            self.assertIn(
                "No source files were changed.",
                result.output,
            )

            self.assertEqual(
                python_path.read_text(encoding="utf-8"),
                python_source,
            )

    def test_unsafe_match_returns_failure_without_diff(
        self,
    ) -> None:
        python_source = dedent(
            '''
            import requests

            payload = {
                "name": "Test User",
                "displayName": "Burak",
            }

            requests.post(
                "http://localhost:3000/users",
                json=payload,
            )
            '''
        ).lstrip()

        with tempfile.TemporaryDirectory() as directory:
            python_path, openapi_path = self._write_files(
                directory=directory,
                python_source=python_source,
            )

            result = self.runner.invoke(
                app,
                [
                    "pytest",
                    "analyze",
                    "--file",
                    str(python_path),
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
                "Decision      : REJECT",
                result.output,
            )
            self.assertIn(
                "Patch suggestion was not generated.",
                result.output,
            )
            self.assertIn(
                "No source files were changed.",
                result.output,
            )
            self.assertNotIn(
                "--- a/",
                result.output,
            )

    @staticmethod
    def _write_files(
        directory: str,
        python_source: str,
    ) -> tuple[Path, Path]:
        directory_path = Path(directory)

        python_path = (
            directory_path / "test_create_user.py"
        )
        openapi_path = directory_path / "openapi.json"

        openapi_document = {
            "openapi": "3.0.0",
            "paths": {
                "/users": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": [
                                            "name",
                                            "email_address",
                                        ],
                                        "properties": {
                                            "name": {
                                                "type": "string",
                                            },
                                            "email_address": {
                                                "type": "string",
                                                "format": "email",
                                            },
                                        },
                                    }
                                }
                            }
                        }
                    }
                }
            },
        }

        python_path.write_text(
            python_source,
            encoding="utf-8",
        )

        openapi_path.write_text(
            json.dumps(openapi_document),
            encoding="utf-8",
        )

        return python_path, openapi_path


if __name__ == "__main__":
    unittest.main()