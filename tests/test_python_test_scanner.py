import tempfile
import unittest
from pathlib import Path

from api_drift_healer.python_test_scanner import (
    PythonTestScanError,
    scan_python_test_files,
)


class PythonTestScannerTests(unittest.TestCase):
    def _write_file(
        self,
        root: Path,
        relative_path: str,
        content: str = "",
    ) -> Path:
        file_path = root / relative_path
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        file_path.write_text(
            content,
            encoding="utf-8",
        )
        return file_path

    def test_finds_test_prefix_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()

            self._write_file(
                root,
                "test_create_user.py",
            )
            self._write_file(
                root,
                "helper.py",
            )

            result = scan_python_test_files(root)

            relative_paths = tuple(
                path.relative_to(root)
                for path in result
            )

            self.assertEqual(
                relative_paths,
                (
                    Path("test_create_user.py"),
                ),
            )

    def test_finds_test_suffix_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()

            self._write_file(
                root,
                "create_user_test.py",
            )

            result = scan_python_test_files(root)

            relative_paths = tuple(
                path.relative_to(root)
                for path in result
            )

            self.assertEqual(
                relative_paths,
                (
                    Path("create_user_test.py"),
                ),
            )

    def test_scans_nested_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()

            self._write_file(
                root,
                "users/test_create_user.py",
            )
            self._write_file(
                root,
                "profiles/nested/profile_test.py",
            )

            result = scan_python_test_files(root)

            relative_paths = tuple(
                path.relative_to(root)
                for path in result
            )

            self.assertEqual(
                relative_paths,
                (
                    Path("profiles/nested/profile_test.py"),
                    Path("users/test_create_user.py"),
                ),
            )

    def test_ignores_excluded_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()

            self._write_file(
                root,
                "test_valid.py",
            )
            self._write_file(
                root,
                "__pycache__/test_cached.py",
            )
            self._write_file(
                root,
                ".venv/test_dependency.py",
            )
            self._write_file(
                root,
                ".git/test_internal.py",
            )

            result = scan_python_test_files(root)

            relative_paths = tuple(
                path.relative_to(root)
                for path in result
            )

            self.assertEqual(
                relative_paths,
                (
                    Path("test_valid.py"),
                ),
            )

    def test_returns_files_in_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()

            self._write_file(
                root,
                "z/test_last.py",
            )
            self._write_file(
                root,
                "a/test_first.py",
            )
            self._write_file(
                root,
                "test_middle.py",
            )

            result = scan_python_test_files(root)

            relative_paths = tuple(
                path.relative_to(root)
                for path in result
            )

            self.assertEqual(
                relative_paths,
                (
                    Path("a/test_first.py"),
                    Path("test_middle.py"),
                    Path("z/test_last.py"),
                ),
            )

    def test_rejects_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_directory = (
                Path(temp_dir).resolve()
                / "missing-tests"
            )

            with self.assertRaises(PythonTestScanError):
                scan_python_test_files(
                    missing_directory,
                )


if __name__ == "__main__":
    unittest.main()
