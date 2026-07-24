import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_drift_healer.python_batch_patch_planner import (
    PythonBatchPatch,
)
from api_drift_healer.python_patch_validator import (
    validate_python_patch,
)


class PythonPatchValidatorFilenameTests(unittest.TestCase):
    @patch(
        "api_drift_healer.python_patch_validator."
        "importlib.util.find_spec",
        return_value=object(),
    )
    @patch(
        "api_drift_healer.python_patch_validator."
        "subprocess.run"
    )
    def test_temporary_pytest_file_has_valid_module_name(
        self,
        run_mock,
        _find_spec_mock,
    ) -> None:
        observed_paths: list[Path] = []

        def fake_run(command, **kwargs):
            node_id = command[3]
            temporary_name, separator, test_name = (
                node_id.partition("::")
            )
            temporary_path = Path(temporary_name)

            self.assertEqual(separator, "::")
            self.assertEqual(test_name, "test_create_user")
            self.assertFalse(
                temporary_path.name.startswith(".")
            )
            self.assertTrue(temporary_path.exists())

            observed_paths.append(temporary_path)

            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout="1 passed",
                stderr="",
            )

        run_mock.side_effect = fake_run

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "test_create_user.py"

            source_path.write_text(
                "def test_create_user():\n"
                "    assert True\n",
                encoding="utf-8",
            )

            patch_item = PythonBatchPatch(
                file_path=source_path,
                test_name="test_create_user",
                method="POST",
                path="/users",
                old_field="userEmail",
                new_field="email_address",
                score=0.772,
                unified_diff="sample diff",
                suggested_source=(
                    "def test_create_user():\n"
                    "    assert True\n"
                ),
            )

            result = validate_python_patch(
                patch=patch_item,
                timeout_seconds=10,
            )

            self.assertTrue(result.validated)
            self.assertEqual(result.status, "PASSED")
            self.assertEqual(len(observed_paths), 1)
            self.assertFalse(observed_paths[0].exists())


if __name__ == "__main__":
    unittest.main()
