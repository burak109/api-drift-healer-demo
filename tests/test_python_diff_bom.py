import json
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from api_drift_healer.python_diff import (
    build_python_patch_suggestion,
)
from api_drift_healer.python_request_analyzer import (
    analyze_python_request_file,
)


class PythonDiffBomTests(unittest.TestCase):
    def test_builds_valid_patch_from_utf8_bom_file(self) -> None:
        python_source = dedent(
            '''
            import requests


            def test_create_user():
                requests.post(
                    "http://localhost:3000/users",
                    json={
                        "name": "Test User",
                        "userEmail": "qa@example.com",
                    },
                )
            '''
        ).lstrip()

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

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            python_path = root / "test_create_user.py"
            openapi_path = root / "openapi.json"

            python_path.write_text(
                python_source,
                encoding="utf-8-sig",
            )
            openapi_path.write_text(
                json.dumps(openapi_document),
                encoding="utf-8",
            )

            analysis_result = analyze_python_request_file(
                python_path=python_path,
                openapi_path=openapi_path,
            )

            self.assertTrue(
                analysis_result.analysis.safe_to_patch
            )

            suggestion = build_python_patch_suggestion(
                analysis_result
            )

            self.assertNotIn(
                "\ufeff",
                suggestion.original_source,
            )
            self.assertNotIn(
                "\ufeff",
                suggestion.suggested_source,
            )
            self.assertIn(
                '"email_address":',
                suggestion.suggested_source,
            )

            compile(
                suggestion.suggested_source,
                str(python_path),
                "exec",
            )


if __name__ == "__main__":
    unittest.main()
