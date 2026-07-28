"""Synchronize one sticky API Drift Healer pull request comment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import requests

from api_drift_healer.github_pr_comment import (
    StickyCommentAction,
    decide_sticky_comment,
)
from api_drift_healer.github_pr_report import COMMENT_MARKER


DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_GITHUB_API_VERSION = "2022-11-28"
DEFAULT_BOT_LOGIN = "github-actions[bot]"


class GitHubApiError(RuntimeError):
    """Raised when GitHub comment synchronization fails."""


@dataclass(frozen=True, slots=True)
class StickyCommentSyncResult:
    """Result of one sticky comment synchronization."""

    action: StickyCommentAction
    comment_id: int


def _validate_repository(repository: str) -> str:
    """Validate an owner/repository GitHub identifier."""

    if not isinstance(repository, str):
        raise GitHubApiError(
            "Repository must be a string."
        )

    normalized = repository.strip()
    parts = normalized.split("/")

    if (
        len(parts) != 2
        or not parts[0]
        or not parts[1]
    ):
        raise GitHubApiError(
            "Repository must use owner/name format."
        )

    return normalized


def _validate_positive_integer(
    value: Any,
    field_name: str,
) -> int:
    """Validate a positive integer input."""

    if type(value) is not int or value <= 0:
        raise GitHubApiError(
            f"{field_name} must be a positive integer."
        )

    return value


def _validate_comment_body(body: str) -> str:
    """Validate one generated sticky comment body."""

    if not isinstance(body, str):
        raise GitHubApiError(
            "Comment body must be a string."
        )

    if not body.strip():
        raise GitHubApiError(
            "Comment body cannot be empty."
        )

    marker_count = body.count(COMMENT_MARKER)

    if marker_count != 1:
        raise GitHubApiError(
            "Comment body must contain exactly one "
            "API Drift Healer marker."
        )

    return body


class GitHubPullRequestCommentClient:
    """Minimal GitHub Issue Comments API client."""

    def __init__(
        self,
        token: str,
        *,
        api_url: str = DEFAULT_GITHUB_API_URL,
        timeout: float = 30.0,
        session: Any | None = None,
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise GitHubApiError(
                "GitHub token cannot be empty."
            )

        if (
            not isinstance(api_url, str)
            or not api_url.strip()
        ):
            raise GitHubApiError(
                "GitHub API URL cannot be empty."
            )

        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise GitHubApiError(
                "GitHub API timeout must be positive."
            )

        self._api_url = api_url.rstrip("/")
        self._timeout = float(timeout)
        self._session = (
            session
            if session is not None
            else requests.Session()
        )
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": (
                f"Bearer {token.strip()}"
            ),
            "X-GitHub-Api-Version": (
                DEFAULT_GITHUB_API_VERSION
            ),
            "User-Agent": "api-drift-healer",
        }

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        """Send one GitHub request and return JSON."""

        url = f"{self._api_url}{path}"

        try:
            response = self._session.request(
                method,
                url,
                headers=self._headers,
                params=params,
                json=payload,
                timeout=self._timeout,
            )
        except requests.RequestException as error:
            raise GitHubApiError(
                "GitHub API request failed."
            ) from error

        if not 200 <= response.status_code < 300:
            raise GitHubApiError(
                "GitHub API returned HTTP "
                f"{response.status_code}."
            )

        try:
            return response.json()
        except ValueError as error:
            raise GitHubApiError(
                "GitHub API returned invalid JSON."
            ) from error

    def list_comments(
        self,
        repository: str,
        pull_request_number: int,
    ) -> tuple[Mapping[str, Any], ...]:
        """List all issue comments for one pull request."""

        repository = _validate_repository(
            repository
        )
        pull_request_number = (
            _validate_positive_integer(
                pull_request_number,
                "Pull request number",
            )
        )

        comments: list[Mapping[str, Any]] = []
        page = 1

        while page <= 100:
            payload = self._request_json(
                "GET",
                (
                    f"/repos/{repository}/issues/"
                    f"{pull_request_number}/comments"
                ),
                params={
                    "per_page": 100,
                    "page": page,
                },
            )

            if not isinstance(payload, list):
                raise GitHubApiError(
                    "GitHub comments response must "
                    "contain a list."
                )

            for index, comment in enumerate(payload):
                if not isinstance(comment, Mapping):
                    raise GitHubApiError(
                        "GitHub comment must be an object "
                        f"at page {page}, index {index}."
                    )

                comments.append(comment)

            if len(payload) < 100:
                return tuple(comments)

            page += 1

        raise GitHubApiError(
            "GitHub comment pagination exceeded "
            "the safety limit."
        )

    def create_comment(
        self,
        repository: str,
        pull_request_number: int,
        body: str,
    ) -> int:
        """Create one pull request issue comment."""

        repository = _validate_repository(
            repository
        )
        pull_request_number = (
            _validate_positive_integer(
                pull_request_number,
                "Pull request number",
            )
        )
        body = _validate_comment_body(body)

        payload = self._request_json(
            "POST",
            (
                f"/repos/{repository}/issues/"
                f"{pull_request_number}/comments"
            ),
            payload={
                "body": body,
            },
        )

        if not isinstance(payload, Mapping):
            raise GitHubApiError(
                "Created comment response must "
                "contain an object."
            )

        return _validate_positive_integer(
            payload.get("id"),
            "Created comment id",
        )

    def update_comment(
        self,
        repository: str,
        comment_id: int,
        body: str,
    ) -> int:
        """Update one existing issue comment."""

        repository = _validate_repository(
            repository
        )
        comment_id = _validate_positive_integer(
            comment_id,
            "Comment id",
        )
        body = _validate_comment_body(body)

        payload = self._request_json(
            "PATCH",
            (
                f"/repos/{repository}/issues/comments/"
                f"{comment_id}"
            ),
            payload={
                "body": body,
            },
        )

        if not isinstance(payload, Mapping):
            raise GitHubApiError(
                "Updated comment response must "
                "contain an object."
            )

        return _validate_positive_integer(
            payload.get("id"),
            "Updated comment id",
        )


def sync_sticky_comment(
    client: GitHubPullRequestCommentClient,
    *,
    repository: str,
    pull_request_number: int,
    body: str,
    expected_author_login: str = DEFAULT_BOT_LOGIN,
) -> StickyCommentSyncResult:
    """Create or update one API Drift Healer PR comment."""

    body = _validate_comment_body(body)

    comments = client.list_comments(
        repository,
        pull_request_number,
    )

    decision = decide_sticky_comment(
        comments,
        expected_author_login=(
            expected_author_login
        ),
    )

    if decision.action is StickyCommentAction.CREATE:
        comment_id = client.create_comment(
            repository,
            pull_request_number,
            body,
        )
    else:
        if decision.comment_id is None:
            raise GitHubApiError(
                "Update decision is missing "
                "a comment id."
            )

        comment_id = client.update_comment(
            repository,
            decision.comment_id,
            body,
        )

    return StickyCommentSyncResult(
        action=decision.action,
        comment_id=comment_id,
    )
