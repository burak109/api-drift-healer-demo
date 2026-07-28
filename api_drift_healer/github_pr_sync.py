"""Publish one sticky API Drift Healer pull request report."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

from api_drift_healer.github_pr_client import (
    DEFAULT_BOT_LOGIN,
    DEFAULT_GITHUB_API_URL,
    GitHubApiError,
    GitHubPullRequestCommentClient,
    StickyCommentSyncResult,
    sync_sticky_comment,
)
from api_drift_healer.github_pr_comment import (
    StickyCommentAction,
    StickyCommentError,
)
from api_drift_healer.github_pr_report import (
    GitHubPullRequestReportError,
    format_github_pr_report_json,
)


class GitHubPullRequestSyncError(RuntimeError):
    """Raised when a pull request report cannot be published."""


def _required_text(
    value: Any,
    field_name: str,
) -> str:
    """Validate one required non-empty string."""

    if not isinstance(value, str) or not value.strip():
        raise GitHubPullRequestSyncError(
            f"{field_name} cannot be empty."
        )

    return value.strip()


def _positive_integer(
    value: Any,
    field_name: str,
) -> int:
    """Validate one positive integer."""

    if type(value) is int:
        parsed_value = value
    elif isinstance(value, str):
        normalized = value.strip()

        if not normalized.isdigit():
            raise GitHubPullRequestSyncError(
                f"{field_name} must be a positive integer."
            )

        parsed_value = int(normalized)
    else:
        raise GitHubPullRequestSyncError(
            f"{field_name} must be a positive integer."
        )

    if parsed_value <= 0:
        raise GitHubPullRequestSyncError(
            f"{field_name} must be a positive integer."
        )

    return parsed_value


def _read_report_json(
    report_path: str | Path,
) -> str:
    """Read one UTF-8 JSON batch report."""

    path = Path(report_path)

    try:
        return path.read_text(
            encoding="utf-8",
        )
    except FileNotFoundError as error:
        raise GitHubPullRequestSyncError(
            f"Batch report file was not found: {path}"
        ) from error
    except IsADirectoryError as error:
        raise GitHubPullRequestSyncError(
            f"Batch report path is not a file: {path}"
        ) from error
    except (OSError, UnicodeError) as error:
        raise GitHubPullRequestSyncError(
            f"Batch report file could not be read: {path}"
        ) from error


def publish_github_pr_report(
    report_path: str | Path,
    *,
    repository: str,
    pull_request_number: int | str,
    token: str | None = None,
    expected_author_login: str = DEFAULT_BOT_LOGIN,
    api_url: str = DEFAULT_GITHUB_API_URL,
    timeout: float = 30.0,
    client: Any | None = None,
) -> StickyCommentSyncResult:
    """Publish one validated sticky pull request report."""

    repository = _required_text(
        repository,
        "Repository",
    )
    pull_request_number = _positive_integer(
        pull_request_number,
        "Pull request number",
    )
    expected_author_login = _required_text(
        expected_author_login,
        "Expected author login",
    )

    report_content = _read_report_json(
        report_path
    )

    try:
        comment_body = format_github_pr_report_json(
            report_content
        )
    except GitHubPullRequestReportError as error:
        raise GitHubPullRequestSyncError(
            f"Batch report validation failed: {error}"
        ) from error

    if client is None:
        token = _required_text(
            token,
            "GitHub token",
        )

        try:
            client = GitHubPullRequestCommentClient(
                token,
                api_url=api_url,
                timeout=timeout,
            )
        except GitHubApiError as error:
            raise GitHubPullRequestSyncError(
                f"GitHub client configuration failed: {error}"
            ) from error

    try:
        return sync_sticky_comment(
            client,
            repository=repository,
            pull_request_number=pull_request_number,
            body=comment_body,
            expected_author_login=(
                expected_author_login
            ),
        )
    except (
        GitHubApiError,
        StickyCommentError,
    ) as error:
        raise GitHubPullRequestSyncError(
            f"Pull request comment sync failed: {error}"
        ) from error


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        prog="api-drift-pr-report",
        description=(
            "Create or update one sticky API Drift "
            "Healer pull request comment."
        ),
    )

    parser.add_argument(
        "--report-json",
        required=True,
        type=Path,
        help="Path to the JSON batch report.",
    )
    parser.add_argument(
        "--repository",
        help=(
            "GitHub repository in owner/name format. "
            "Defaults to GITHUB_REPOSITORY."
        ),
    )
    parser.add_argument(
        "--pull-request-number",
        help=(
            "Pull request number. Defaults to "
            "API_DRIFT_PULL_REQUEST_NUMBER."
        ),
    )
    parser.add_argument(
        "--expected-author-login",
        help=(
            "Expected owner of an existing marker "
            "comment. Defaults to github-actions[bot]."
        ),
    )
    parser.add_argument(
        "--api-url",
        help=(
            "GitHub API base URL. "
            "Defaults to GITHUB_API_URL."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="GitHub API timeout in seconds.",
    )

    return parser


def _environment_value(
    environ: Mapping[str, str],
    name: str,
) -> str | None:
    """Return one normalized environment value."""

    value = environ.get(name)

    if value is None:
        return None

    normalized = value.strip()

    return normalized or None


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    client: Any | None = None,
) -> int:
    """Run the pull request reporting command."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)

    environ = (
        os.environ
        if environ is None
        else environ
    )
    stdout = (
        sys.stdout
        if stdout is None
        else stdout
    )
    stderr = (
        sys.stderr
        if stderr is None
        else stderr
    )

    repository = (
        arguments.repository
        or _environment_value(
            environ,
            "GITHUB_REPOSITORY",
        )
    )
    pull_request_number = (
        arguments.pull_request_number
        or _environment_value(
            environ,
            "API_DRIFT_PULL_REQUEST_NUMBER",
        )
    )
    token = _environment_value(
        environ,
        "GITHUB_TOKEN",
    )
    expected_author_login = (
        arguments.expected_author_login
        or _environment_value(
            environ,
            "API_DRIFT_EXPECTED_AUTHOR_LOGIN",
        )
        or DEFAULT_BOT_LOGIN
    )
    api_url = (
        arguments.api_url
        or _environment_value(
            environ,
            "GITHUB_API_URL",
        )
        or DEFAULT_GITHUB_API_URL
    )

    try:
        result = publish_github_pr_report(
            arguments.report_json,
            repository=repository or "",
            pull_request_number=(
                pull_request_number or ""
            ),
            token=token,
            expected_author_login=(
                expected_author_login
            ),
            api_url=api_url,
            timeout=arguments.timeout,
            client=client,
        )
    except GitHubPullRequestSyncError as error:
        print(
            f"Error: {error}",
            file=stderr,
        )
        return 1

    action_text = {
        StickyCommentAction.CREATE: "created",
        StickyCommentAction.UPDATE: "updated",
    }[result.action]

    print(
        (
            "API Drift Healer pull request comment "
            f"{action_text}: {result.comment_id}"
        ),
        file=stdout,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
