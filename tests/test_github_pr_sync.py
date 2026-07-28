import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from api_drift_healer.github_pr_comment import (
    StickyCommentAction,
)
from api_drift_healer.github_pr_report import (
    COMMENT_MARKER,
)
from api_drift_healer.github_pr_sync import (
    GitHubPullRequestSyncError,
    main,
    publish_github_pr_report,
)


class FakeCommentClient:
    def __init__(
        self,
        comments: tuple[dict[str, Any], ...] = (),
    ) -> None:
        self.comments = comments
        self.calls: list[tuple[Any, ...]] = []

    def list_comments(
        self,
        repository: str,
        pull_request_number: int,
    ) -> tuple[dict[str, Any], ...]:
        self.calls.append(
            (
                "list",
                repository,
                pull_request_number,
            )
        )

        return self.comments

    def create_comment(
        self,
        repository: str,
        pull_request_number: int,
        body: str,
    ) -> int:
        self.calls.append(
            (
                "create",
                repository,
                pull_request_number,
                body,
            )
        )

        return 101

    def update_comment(
        self,
        repository: str,
        comment_id: int,
        body: str,
    ) -> int:
        self.calls.append(
            (
                "update",
                repository,
                comment_id,
                body,
            )
        )

        return comment_id


class GitHubPullRequestSyncTests(unittest.TestCase):
    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "files_scanned": 3,
            "requests_discovered": 3,
            "requests_analyzed": 3,
            "no_drift": 2,
            "drifts_detected": 1,
            "safe_patch_decisions": 1,
            "rejected_drifts": 0,
            "complex_drifts": 0,
            "patches_generated": 1,
            "patches_validated": 1,
            "validation_failures": 0,
            "pipeline_errors": 0,
            "source_files_changed": False,
        }

    def _report_file(
        self,
        directory: str,
        payload: object | None = None,
    ) -> Path:
        path = Path(directory) / "report.json"

        path.write_text(
            json.dumps(
                self._payload()
                if payload is None
                else payload
            ),
            encoding="utf-8",
        )

        return path

    def test_publishes_new_comment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path = self._report_file(
                directory
            )
            client = FakeCommentClient()

            result = publish_github_pr_report(
                report_path,
                repository="owner/repository",
                pull_request_number=12,
                client=client,
            )

        self.assertEqual(
            result.action,
            StickyCommentAction.CREATE,
        )
        self.assertEqual(result.comment_id, 101)
        self.assertEqual(
            [
                call[0]
                for call in client.calls
            ],
            [
                "list",
                "create",
            ],
        )

        generated_body = client.calls[1][3]

        self.assertIn(
            COMMENT_MARKER,
            generated_body,
        )
        self.assertIn(
            "API Drift Healer Report",
            generated_body,
        )

    def test_updates_existing_comment(self) -> None:
        existing_body = (
            f"{COMMENT_MARKER}\n\n"
            "Old report"
        )
        client = FakeCommentClient(
            comments=(
                {
                    "id": 77,
                    "body": existing_body,
                    "user": {
                        "login": (
                            "github-actions[bot]"
                        ),
                    },
                },
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            report_path = self._report_file(
                directory
            )

            result = publish_github_pr_report(
                report_path,
                repository="owner/repository",
                pull_request_number="12",
                client=client,
            )

        self.assertEqual(
            result.action,
            StickyCommentAction.UPDATE,
        )
        self.assertEqual(result.comment_id, 77)
        self.assertEqual(
            client.calls[1][0],
            "update",
        )
        self.assertEqual(
            client.calls[1][2],
            77,
        )

    def test_rejects_missing_report_file(self) -> None:
        client = FakeCommentClient()

        with self.assertRaisesRegex(
            GitHubPullRequestSyncError,
            "was not found",
        ):
            publish_github_pr_report(
                "/missing/report.json",
                repository="owner/repository",
                pull_request_number=12,
                client=client,
            )

    def test_rejects_invalid_report_json(self) -> None:
        client = FakeCommentClient()

        with tempfile.TemporaryDirectory() as directory:
            report_path = (
                Path(directory) / "report.json"
            )
            report_path.write_text(
                "{invalid-json",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                GitHubPullRequestSyncError,
                "validation failed",
            ):
                publish_github_pr_report(
                    report_path,
                    repository="owner/repository",
                    pull_request_number=12,
                    client=client,
                )

    def test_rejects_invalid_pull_request_number(
        self,
    ) -> None:
        client = FakeCommentClient()

        with tempfile.TemporaryDirectory() as directory:
            report_path = self._report_file(
                directory
            )

            with self.assertRaisesRegex(
                GitHubPullRequestSyncError,
                "positive integer",
            ):
                publish_github_pr_report(
                    report_path,
                    repository="owner/repository",
                    pull_request_number="abc",
                    client=client,
                )

    def test_main_reads_github_environment(
        self,
    ) -> None:
        client = FakeCommentClient()
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as directory:
            report_path = self._report_file(
                directory
            )

            exit_code = main(
                [
                    "--report-json",
                    str(report_path),
                ],
                environ={
                    "GITHUB_REPOSITORY": (
                        "owner/repository"
                    ),
                    "GITHUB_TOKEN": "secret-token",
                    (
                        "API_DRIFT_"
                        "PULL_REQUEST_NUMBER"
                    ): "12",
                },
                stdout=stdout,
                stderr=stderr,
                client=client,
            )

        self.assertEqual(exit_code, 0)
        self.assertIn(
            "comment created: 101",
            stdout.getvalue(),
        )
        self.assertEqual(
            stderr.getvalue(),
            "",
        )

    def test_main_reports_missing_repository(
        self,
    ) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as directory:
            report_path = self._report_file(
                directory
            )

            exit_code = main(
                [
                    "--report-json",
                    str(report_path),
                ],
                environ={
                    "GITHUB_TOKEN": "secret-token",
                    (
                        "API_DRIFT_"
                        "PULL_REQUEST_NUMBER"
                    ): "12",
                },
                stdout=stdout,
                stderr=stderr,
                client=FakeCommentClient(),
            )

        self.assertEqual(exit_code, 1)
        self.assertIn(
            "Repository cannot be empty",
            stderr.getvalue(),
        )

    def test_main_reports_missing_pr_number(
        self,
    ) -> None:
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as directory:
            report_path = self._report_file(
                directory
            )

            exit_code = main(
                [
                    "--report-json",
                    str(report_path),
                ],
                environ={
                    "GITHUB_REPOSITORY": (
                        "owner/repository"
                    ),
                    "GITHUB_TOKEN": "secret-token",
                },
                stderr=stderr,
                client=FakeCommentClient(),
            )

        self.assertEqual(exit_code, 1)
        self.assertIn(
            "Pull request number",
            stderr.getvalue(),
        )

    def test_main_does_not_print_token(
        self,
    ) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        secret_token = "super-secret-token"

        with tempfile.TemporaryDirectory() as directory:
            report_path = self._report_file(
                directory
            )

            exit_code = main(
                [
                    "--report-json",
                    str(report_path),
                ],
                environ={
                    "GITHUB_REPOSITORY": (
                        "owner/repository"
                    ),
                    "GITHUB_TOKEN": secret_token,
                    (
                        "API_DRIFT_"
                        "PULL_REQUEST_NUMBER"
                    ): "12",
                },
                stdout=stdout,
                stderr=stderr,
                client=FakeCommentClient(),
            )

        combined_output = (
            stdout.getvalue()
            + stderr.getvalue()
        )

        self.assertEqual(exit_code, 0)
        self.assertNotIn(
            secret_token,
            combined_output,
        )

    def test_main_reports_invalid_report(
        self,
    ) -> None:
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as directory:
            report_path = (
                Path(directory) / "report.json"
            )
            report_path.write_text(
                "[]",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--report-json",
                    str(report_path),
                ],
                environ={
                    "GITHUB_REPOSITORY": (
                        "owner/repository"
                    ),
                    "GITHUB_TOKEN": "secret-token",
                    (
                        "API_DRIFT_"
                        "PULL_REQUEST_NUMBER"
                    ): "12",
                },
                stderr=stderr,
                client=FakeCommentClient(),
            )

        self.assertEqual(exit_code, 1)
        self.assertIn(
            "validation failed",
            stderr.getvalue(),
        )

    def test_cli_arguments_override_environment(
        self,
    ) -> None:
        client = FakeCommentClient()

        with tempfile.TemporaryDirectory() as directory:
            report_path = self._report_file(
                directory
            )

            exit_code = main(
                [
                    "--report-json",
                    str(report_path),
                    "--repository",
                    "argument/repository",
                    "--pull-request-number",
                    "99",
                ],
                environ={
                    "GITHUB_REPOSITORY": (
                        "environment/repository"
                    ),
                    "GITHUB_TOKEN": "secret-token",
                    (
                        "API_DRIFT_"
                        "PULL_REQUEST_NUMBER"
                    ): "12",
                },
                client=client,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            client.calls[0],
            (
                "list",
                "argument/repository",
                99,
            ),
        )


if __name__ == "__main__":
    unittest.main()
