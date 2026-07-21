import os
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "demo_postman.sh"
COLLECTION_PATH = (
    PROJECT_ROOT
    / "examples"
    / "postman"
    / "create-user.postman_collection.json"
)


class PostmanDemoScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.original_collection_before = (
            COLLECTION_PATH.read_bytes()
        )

        cls.result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        cls.original_collection_after = (
            COLLECTION_PATH.read_bytes()
        )

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
            "POSTMAN DEMO COMPLETED SUCCESSFULLY",
            self.result.stdout,
        )

    def test_demo_preserves_original_collection(self) -> None:
        self.assertEqual(
            self.original_collection_before,
            self.original_collection_after,
        )

        self.assertIn(
            "PASS: original collection was preserved.",
            self.result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
