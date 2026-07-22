import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from api_drift_healer.newman_runner import (
    NewmanNotFoundError,
    NewmanRunnerError,
    NewmanTimeoutError,
    _build_execution_command,
    find_newman_executable,
    run_newman_collection,
)


def create_json_file(
    directory: Path,
    name: str,
) -> Path:
    """Create a minimal JSON file for runner tests."""

    file_path = directory / name
    file_path.write_text(
        "{}",
        encoding="utf-8",
    )

    return file_path


class NewmanRunnerTests(unittest.TestCase):
    def test_find_newman_executable_prefers_windows_cmd_shim(
        self,
    ) -> None:
        with (
            patch(
                "api_drift_healer.newman_runner.os.name",
                "nt",
            ),
            patch(
                "api_drift_healer.newman_runner.shutil.which",
                side_effect=[
                    r"C:\Tools\newman.cmd",
                    None,
                    None,
                ],
            ) as which_mock,
        ):
            executable = find_newman_executable()

        self.assertEqual(
            executable,
            r"C:\Tools\newman.cmd",
        )

        self.assertEqual(
            which_mock.call_args_list[0],
            call("newman.cmd"),
        )

    def test_find_newman_executable_returns_none_when_missing(
        self,
    ) -> None:
        with patch(
            "api_drift_healer.newman_runner.shutil.which",
            return_value=None,
        ):
            executable = find_newman_executable()

        self.assertIsNone(executable)

    def test_successful_run_returns_passed_result(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_path = Path(directory)

            collection_path = create_json_file(
                temp_path,
                "collection.json",
            )

            environment_path = create_json_file(
                temp_path,
                "environment.json",
            )

            completed_process = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="2 assertions passed",
                stderr="",
            )

            with patch(
                "api_drift_healer.newman_runner.subprocess.run",
                return_value=completed_process,
            ) as run_mock:
                result = run_newman_collection(
                    collection_path=collection_path,
                    environment_path=environment_path,
                    timeout_seconds=30,
                    newman_executable="newman",
                )

        self.assertTrue(result.passed)
        self.assertFalse(result.failed)
        self.assertEqual(result.return_code, 0)

        self.assertEqual(
            result.command,
            (
                "newman",
                "run",
                str(collection_path.resolve()),
                "--environment",
                str(environment_path.resolve()),
            ),
        )

        run_mock.assert_called_once()

        run_kwargs = run_mock.call_args.kwargs

        self.assertEqual(
            run_kwargs["cwd"],
            collection_path.resolve().parent,
        )

        self.assertEqual(
            run_kwargs["timeout"],
            30,
        )

        self.assertFalse(
            run_kwargs["check"]
        )

    def test_failed_newman_run_is_returned_not_raised(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            collection_path = create_json_file(
                Path(directory),
                "collection.json",
            )

            completed_process = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="1 assertion failed",
                stderr="",
            )

            with patch(
                "api_drift_healer.newman_runner.subprocess.run",
                return_value=completed_process,
            ):
                result = run_newman_collection(
                    collection_path=collection_path,
                    newman_executable="newman",
                )

        self.assertFalse(result.passed)
        self.assertTrue(result.failed)
        self.assertEqual(result.return_code, 1)
        self.assertIn(
            "assertion failed",
            result.stdout,
        )

    def test_missing_collection_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_path = (
                Path(directory)
                / "missing-collection.json"
            )

            with self.assertRaisesRegex(
                NewmanRunnerError,
                "Postman collection does not exist",
            ):
                run_newman_collection(
                    collection_path=missing_path,
                    newman_executable="newman",
                )

    def test_missing_environment_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_path = Path(directory)

            collection_path = create_json_file(
                temp_path,
                "collection.json",
            )

            missing_environment = (
                temp_path
                / "missing-environment.json"
            )

            with self.assertRaisesRegex(
                NewmanRunnerError,
                "Postman environment does not exist",
            ):
                run_newman_collection(
                    collection_path=collection_path,
                    environment_path=missing_environment,
                    newman_executable="newman",
                )

    def test_missing_newman_executable_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            collection_path = create_json_file(
                Path(directory),
                "collection.json",
            )

            with (
                patch(
                    "api_drift_healer.newman_runner."
                    "find_newman_executable",
                    return_value=None,
                ),
                self.assertRaisesRegex(
                    NewmanNotFoundError,
                    "Newman executable was not found",
                ),
            ):
                run_newman_collection(
                    collection_path=collection_path,
                )

    def test_timeout_is_raised_as_runner_error(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            collection_path = create_json_file(
                Path(directory),
                "collection.json",
            )

            timeout_error = subprocess.TimeoutExpired(
                cmd="newman",
                timeout=5,
            )

            with (
                patch(
                    "api_drift_healer.newman_runner.subprocess.run",
                    side_effect=timeout_error,
                ),
                self.assertRaisesRegex(
                    NewmanTimeoutError,
                    "exceeded the timeout",
                ),
            ):
                run_newman_collection(
                    collection_path=collection_path,
                    timeout_seconds=5,
                    newman_executable="newman",
                )

    def test_windows_cmd_shim_uses_command_processor(
        self,
    ) -> None:
        logical_command = (
            r"C:\Program Files\nodejs\newman.cmd",
            "run",
            r"C:\API Tests\collection.json",
        )

        with (
            patch(
                "api_drift_healer.newman_runner.os.name",
                "nt",
            ),
            patch.dict(
                os.environ,
                {
                    "COMSPEC": (
                        r"C:\Windows\System32\cmd.exe"
                    )
                },
            ),
        ):
            execution_command = (
                _build_execution_command(
                    logical_command
                )
            )

        self.assertEqual(
            execution_command[:4],
            [
                r"C:\Windows\System32\cmd.exe",
                "/d",
                "/s",
                "/c",
            ],
        )

        self.assertIn(
            "newman.cmd",
            execution_command[4],
        )

        self.assertIn(
            "collection.json",
            execution_command[4],
        )


if __name__ == "__main__":
    unittest.main()