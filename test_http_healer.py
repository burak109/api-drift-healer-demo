import tempfile
import unittest
from pathlib import Path

from api_drift_healer.http_healer import (
    heal_http_file,
)


OPENAPI_TEXT = """\
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /users:
    post:
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - name
                - email_address
              properties:
                name:
                  type: string
                email_address:
                  type: string
                  format: email
"""


HTTP_TEXT = """\
POST http://localhost:3000/users
Content-Type: application/json

{
  "name": "Test User",
  "userEmail": "qa_user@example.com"
}
"""


class HttpHealerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.directory = Path(
            self.temp_directory.name
        )

        self.http_path = (
            self.directory / "create-user.http"
        )

        self.openapi_path = (
            self.directory / "openapi.yaml"
        )

        self.http_path.write_text(
            HTTP_TEXT,
            encoding="utf-8",
        )

        self.openapi_path.write_text(
            OPENAPI_TEXT,
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_dry_run_detects_and_patches_safe_drift(
        self,
    ) -> None:
        result = heal_http_file(
            file_path=self.http_path,
            openapi_path=self.openapi_path,
            dry_run=True,
        )

        self.assertEqual(
            result.analysis.decision,
            "SAFE_PATCH",
        )

        self.assertEqual(
            result.analysis.old_field,
            "userEmail",
        )

        self.assertEqual(
            result.analysis.new_field,
            "email_address",
        )

        self.assertFalse(result.written)

        self.assertIn(
            '-  "userEmail":',
            result.diff,
        )

        self.assertIn(
            '+  "email_address":',
            result.diff,
        )

        self.assertEqual(
            self.http_path.read_text(
                encoding="utf-8"
            ),
            HTTP_TEXT,
        )

    def test_writes_separate_healed_http_file(
        self,
    ) -> None:
        result = heal_http_file(
            file_path=self.http_path,
            openapi_path=self.openapi_path,
        )

        self.assertTrue(result.written)
        self.assertIsNotNone(result.output_path)

        assert result.output_path is not None

        self.assertEqual(
            result.output_path.name,
            "create-user.healed.http",
        )

        healed_text = result.output_path.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '"email_address": "qa_user@example.com"',
            healed_text,
        )

        self.assertNotIn(
            '"userEmail": "qa_user@example.com"',
            healed_text,
        )

        self.assertEqual(
            self.http_path.read_text(
                encoding="utf-8"
            ),
            HTTP_TEXT,
        )


if __name__ == "__main__":
    unittest.main()