import tempfile
import unittest
from pathlib import Path

from api_drift_healer.python_batch_scanner import (
    scan_python_test_requests,
)


class PythonBatchScannerTests(unittest.TestCase):
    def _write_file(
        self,
        root: Path,
        relative_path: str,
        content: str,
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

    def test_collects_requests_from_multiple_test_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self._write_file(
                root,
                "test_create_user.py",
                '''
import requests


def test_create_user():
    requests.post(
        "http://localhost:3000/users",
        json={"userEmail": "create@example.com"},
    )
''',
            )

            self._write_file(
                root,
                "users/update_user_test.py",
                '''
import requests


def test_update_user():
    requests.put(
        "http://localhost:3000/users/1",
        json={"userEmail": "update@example.com"},
    )
''',
            )

            result = scan_python_test_requests(root)

            self.assertEqual(result.files_scanned, 2)
            self.assertEqual(len(result.requests), 2)
            self.assertEqual(result.errors, ())

            self.assertEqual(
                result.requests[0].file_path.relative_to(root),
                Path("test_create_user.py"),
            )
            self.assertEqual(
                result.requests[0].request.test_name,
                "test_create_user",
            )
            self.assertEqual(
                result.requests[0].request.method,
                "POST",
            )

            self.assertEqual(
                result.requests[1].file_path.relative_to(root),
                Path("users/update_user_test.py"),
            )
            self.assertEqual(
                result.requests[1].request.test_name,
                "test_update_user",
            )
            self.assertEqual(
                result.requests[1].request.method,
                "PUT",
            )

    def test_collects_multiple_requests_from_one_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self._write_file(
                root,
                "test_users.py",
                '''
import requests


def test_create_and_update_user():
    requests.post(
        "http://localhost:3000/users",
        json={"userEmail": "create@example.com"},
    )

    requests.patch(
        "http://localhost:3000/users/1",
        json={"userEmail": "update@example.com"},
    )
''',
            )

            result = scan_python_test_requests(root)

            self.assertEqual(result.files_scanned, 1)
            self.assertEqual(len(result.requests), 2)

            self.assertEqual(
                tuple(
                    item.request.method
                    for item in result.requests
                ),
                (
                    "POST",
                    "PATCH",
                ),
            )

            self.assertEqual(
                tuple(
                    item.request.test_name
                    for item in result.requests
                ),
                (
                    "test_create_and_update_user",
                    "test_create_and_update_user",
                ),
            )

    def test_continues_when_one_file_has_invalid_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self._write_file(
                root,
                "test_valid.py",
                '''
import requests


def test_valid():
    requests.post(
        "http://localhost:3000/users",
        json={"userEmail": "valid@example.com"},
    )
''',
            )

            self._write_file(
                root,
                "test_invalid.py",
                '''
def test_invalid(
''',
            )

            result = scan_python_test_requests(root)

            self.assertEqual(result.files_scanned, 2)
            self.assertEqual(len(result.requests), 1)
            self.assertEqual(len(result.errors), 1)

            error = result.errors[0]

            self.assertEqual(
                error.file_path.relative_to(root),
                Path("test_invalid.py"),
            )
            self.assertIn(
                "could not be parsed",
                error.message,
            )

    def test_returns_requests_in_deterministic_file_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            for relative_path, method in (
                ("z/test_last.py", "patch"),
                ("a/test_first.py", "post"),
                ("test_middle.py", "put"),
            ):
                self._write_file(
                    root,
                    relative_path,
                    f'''
import requests


def test_request():
    requests.{method}(
        "http://localhost:3000/users",
        json={{"userEmail": "qa@example.com"}},
    )
''',
                )

            result = scan_python_test_requests(root)

            relative_paths = tuple(
                item.file_path.relative_to(root)
                for item in result.requests
            )

            self.assertEqual(
                relative_paths,
                (
                    Path("a/test_first.py"),
                    Path("test_middle.py"),
                    Path("z/test_last.py"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
