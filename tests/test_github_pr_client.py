import unittest
from typing import Any

from api_drift_healer.github_pr_client import (
    GitHubApiError,
    GitHubPullRequestCommentClient,
    sync_sticky_comment,
)
from api_drift_healer.github_pr_comment import (
    StickyCommentAction,
)
from api_drift_healer.github_pr_report import (
    COMMENT_MARKER,
)


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: Any,
    ) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload

        return self._payload


class FakeSession:
    def __init__(
        self,
        responses: list[FakeResponse],
    ) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                **kwargs,
            }
        )

        if not self.responses:
            raise AssertionError(
                "No fake response remains."
            )

        return self.responses.pop(0)


class GitHubPullRequestCommentClientTests(
    unittest.TestCase
):
    def _body(self) -> str:
        return (
            f"{COMMENT_MARKER}\n\n"
            "## API Drift Healer Report"
        )

    def _client(
        self,
        responses: list[FakeResponse],
    ) -> tuple[
        GitHubPullRequestCommentClient,
        FakeSession,
    ]:
        session = FakeSession(responses)

        client = GitHubPullRequestCommentClient(
            "secret-token",
            session=session,
        )

        return client, session

    def test_lists_pull_request_comments(self) -> None:
        client, session = self._client(
            [
                FakeResponse(
                    200,
                    [
                        {
                            "id": 10,
                            "body": "Reviewer comment",
                        }
                    ],
                )
            ]
        )

        comments = client.list_comments(
            "owner/repository",
            12,
        )

        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["id"], 10)

        call = session.calls[0]

        self.assertEqual(call["method"], "GET")
        self.assertEqual(
            call["url"],
            (
                "https://api.github.com/repos/"
                "owner/repository/issues/12/comments"
            ),
        )
        self.assertEqual(
            call["params"],
            {
                "per_page": 100,
                "page": 1,
            },
        )
        self.assertEqual(
            call["headers"]["Authorization"],
            "Bearer secret-token",
        )

    def test_lists_paginated_comments(self) -> None:
        first_page = [
            {
                "id": index + 1,
                "body": "Comment",
            }
            for index in range(100)
        ]

        client, session = self._client(
            [
                FakeResponse(200, first_page),
                FakeResponse(
                    200,
                    [
                        {
                            "id": 101,
                            "body": "Last comment",
                        }
                    ],
                ),
            ]
        )

        comments = client.list_comments(
            "owner/repository",
            12,
        )

        self.assertEqual(len(comments), 101)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(
            session.calls[1]["params"]["page"],
            2,
        )

    def test_creates_comment(self) -> None:
        client, session = self._client(
            [
                FakeResponse(
                    201,
                    {
                        "id": 55,
                    },
                )
            ]
        )

        comment_id = client.create_comment(
            "owner/repository",
            12,
            self._body(),
        )

        self.assertEqual(comment_id, 55)

        call = session.calls[0]

        self.assertEqual(call["method"], "POST")
        self.assertEqual(
            call["json"],
            {
                "body": self._body(),
            },
        )

    def test_updates_comment(self) -> None:
        client, session = self._client(
            [
                FakeResponse(
                    200,
                    {
                        "id": 55,
                    },
                )
            ]
        )

        comment_id = client.update_comment(
            "owner/repository",
            55,
            self._body(),
        )

        self.assertEqual(comment_id, 55)

        call = session.calls[0]

        self.assertEqual(call["method"], "PATCH")
        self.assertTrue(
            call["url"].endswith(
                "/issues/comments/55"
            )
        )

    def test_sync_creates_missing_comment(self) -> None:
        client, session = self._client(
            [
                FakeResponse(200, []),
                FakeResponse(
                    201,
                    {
                        "id": 88,
                    },
                ),
            ]
        )

        result = sync_sticky_comment(
            client,
            repository="owner/repository",
            pull_request_number=12,
            body=self._body(),
        )

        self.assertEqual(
            result.action,
            StickyCommentAction.CREATE,
        )
        self.assertEqual(result.comment_id, 88)
        self.assertEqual(
            [
                call["method"]
                for call in session.calls
            ],
            [
                "GET",
                "POST",
            ],
        )

    def test_sync_updates_existing_comment(self) -> None:
        client, session = self._client(
            [
                FakeResponse(
                    200,
                    [
                        {
                            "id": 88,
                            "body": self._body(),
                            "user": {
                                "login": (
                                    "github-actions[bot]"
                                ),
                            },
                        }
                    ],
                ),
                FakeResponse(
                    200,
                    {
                        "id": 88,
                    },
                ),
            ]
        )

        result = sync_sticky_comment(
            client,
            repository="owner/repository",
            pull_request_number=12,
            body=self._body(),
        )

        self.assertEqual(
            result.action,
            StickyCommentAction.UPDATE,
        )
        self.assertEqual(result.comment_id, 88)
        self.assertEqual(
            [
                call["method"]
                for call in session.calls
            ],
            [
                "GET",
                "PATCH",
            ],
        )

    def test_rejects_http_error(self) -> None:
        client, _ = self._client(
            [
                FakeResponse(
                    403,
                    {
                        "message": "Forbidden",
                    },
                )
            ]
        )

        with self.assertRaisesRegex(
            GitHubApiError,
            "HTTP 403",
        ):
            client.list_comments(
                "owner/repository",
                12,
            )

    def test_rejects_invalid_json(self) -> None:
        client, _ = self._client(
            [
                FakeResponse(
                    200,
                    ValueError("invalid JSON"),
                )
            ]
        )

        with self.assertRaisesRegex(
            GitHubApiError,
            "invalid JSON",
        ):
            client.list_comments(
                "owner/repository",
                12,
            )

    def test_rejects_non_list_comment_response(
        self,
    ) -> None:
        client, _ = self._client(
            [
                FakeResponse(
                    200,
                    {
                        "unexpected": "object",
                    },
                )
            ]
        )

        with self.assertRaisesRegex(
            GitHubApiError,
            "must contain a list",
        ):
            client.list_comments(
                "owner/repository",
                12,
            )

    def test_rejects_invalid_repository(self) -> None:
        client, _ = self._client([])

        with self.assertRaisesRegex(
            GitHubApiError,
            "owner/name",
        ):
            client.list_comments(
                "repository-only",
                12,
            )

    def test_rejects_body_without_marker(self) -> None:
        client, _ = self._client([])

        with self.assertRaisesRegex(
            GitHubApiError,
            "exactly one",
        ):
            client.create_comment(
                "owner/repository",
                12,
                "No marker",
            )

    def test_rejects_empty_token(self) -> None:
        with self.assertRaisesRegex(
            GitHubApiError,
            "token cannot be empty",
        ):
            GitHubPullRequestCommentClient(" ")


if __name__ == "__main__":
    unittest.main()
