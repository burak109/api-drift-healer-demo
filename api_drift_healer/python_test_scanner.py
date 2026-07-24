"""Discover Python test files inside a directory tree."""

from __future__ import annotations

import os
from pathlib import Path


class PythonTestScanError(ValueError):
    """Raised when a Python test directory cannot be scanned."""


_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
    }
)


def scan_python_test_files(
    directory: str | Path,
) -> tuple[Path, ...]:
    """Return Python test files found under the given directory.

    Supported file patterns:

    - test_*.py
    - *_test.py
    """

    root = Path(directory).expanduser().resolve()

    if not root.exists():
        raise PythonTestScanError(
            f"Test directory does not exist: {root}"
        )

    if not root.is_dir():
        raise PythonTestScanError(
            f"Test path is not a directory: {root}"
        )

    discovered_files: list[Path] = []

    for current_directory, directory_names, file_names in os.walk(root):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in _EXCLUDED_DIRECTORIES
        )

        current_path = Path(current_directory)

        for file_name in sorted(file_names):
            if not _is_python_test_file(file_name):
                continue

            discovered_files.append(
                current_path / file_name
            )

    return tuple(
        sorted(
            discovered_files,
            key=lambda path: (
                path.relative_to(root)
                .as_posix()
                .casefold()
            ),
        )
    )


def _is_python_test_file(file_name: str) -> bool:
    """Return whether a filename matches a supported test pattern."""

    if not file_name.endswith(".py"):
        return False

    return (
        file_name.startswith("test_")
        or file_name.endswith("_test.py")
    )
