import os
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "demo_http.sh"
HTTP_PATH = (
    PROJECT_ROOT
    / "examples"
    / "http"
    / "create-user.http"
)


class HttpDemoScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.original_http_before = HTTP_PATH.read_bytes()

        cls.result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        cls.original_http_after = HTTP_PATH.read_bytes()

    def test_demo_script_is_executable(self) -> None:
        self.assertTrue(
            os.access(SCRIPT_PATH, os.X_OK)
        )

    def test_demo_script_completes_successfully(self) -> None:
        self.assertEqual(
            self.result.returncode,
            0,
            msg=(
                self.result.stdout
                + "\n"
                + self.result.stderr
            ),
        )

        self.assertIn(
            "Decision: SAFE_PATCH",
            self.result.stdout,
        )

        self.assertIn(
            "userEmail -> email_address",
            self.result.stdout,
        )

        self.assertIn(
            "PASS: request formatting was preserved.",
            self.result.stdout,
        )

        self.assertIn(
            "HTTP FILE DEMO COMPLETED SUCCESSFULLY",
            self.result.stdout,
        )

    def test_demo_preserves_original_http_file(self) -> None:
        self.assertEqual(
            self.original_http_before,
            self.original_http_after,
        )

        self.assertIn(
            "PASS: original HTTP file was preserved.",
            self.result.stdout,
        )


if __name__ == "__main__":
    unittest.main()     