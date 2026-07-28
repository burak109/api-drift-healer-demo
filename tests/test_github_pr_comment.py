import unittest

from api_drift_healer.github_pr_comment import (
    StickyCommentAction,
    StickyCommentError,
    decide_sticky_comment,
)
from api_drift_healer.github_pr_report import (
    COMMENT_MARKER,
)


class StickyPullRequestCommentTests(unittest.TestCase):
    def test_creates_when_comment_list_is_empty(self) -> None:
        decision = decide_sticky_comment(())

        self.assertEqual(
            decision.action,
            StickyCommentAction.CREATE,
        )
        self.assertIsNone(decision.comment_id)

    def test_creates_when_marker_is_not_found(self) -> None:
        comments = (
            {
                "id": 10,
                "body": "Normal reviewer comment.",
            },
        )

        decision = decide_sticky_comment(comments)

        self.assertEqual(
            decision.action,
            StickyCommentAction.CREATE,
        )

    def test_updates_one_existing_marker_comment(self) -> None:
        comments = (
            {
                "id": 42,
                "body": (
                    f"{COMMENT_MARKER}\n\n"
                    "## API Drift Healer Report"
                ),
                "user": {
                    "login": "github-actions[bot]",
                },
            },
        )

        decision = decide_sticky_comment(
            comments,
            expected_author_login=(
                "github-actions[bot]"
            ),
        )

        self.assertEqual(
            decision.action,
            StickyCommentAction.UPDATE,
        )
        self.assertEqual(decision.comment_id, 42)

    def test_rejects_multiple_marker_comments(self) -> None:
        comments = (
            {
                "id": 41,
                "body": COMMENT_MARKER,
            },
            {
                "id": 42,
                "body": COMMENT_MARKER,
            },
        )

        with self.assertRaisesRegex(
            StickyCommentError,
            "Multiple sticky marker comments",
        ):
            decide_sticky_comment(comments)

    def test_rejects_duplicate_marker_in_one_comment(
        self,
    ) -> None:
        comments = (
            {
                "id": 42,
                "body": (
                    f"{COMMENT_MARKER}\n"
                    f"{COMMENT_MARKER}"
                ),
            },
        )

        with self.assertRaisesRegex(
            StickyCommentError,
            "appears more than once",
        ):
            decide_sticky_comment(comments)

    def test_rejects_invalid_marker_comment_id(
        self,
    ) -> None:
        comments = (
            {
                "id": "42",
                "body": COMMENT_MARKER,
            },
        )

        with self.assertRaisesRegex(
            StickyCommentError,
            "positive integer id",
        ):
            decide_sticky_comment(comments)

    def test_rejects_non_string_comment_body(
        self,
    ) -> None:
        comments = (
            {
                "id": 42,
                "body": {
                    "unexpected": "object",
                },
            },
        )

        with self.assertRaisesRegex(
            StickyCommentError,
            "body must be a string",
        ):
            decide_sticky_comment(comments)

    def test_rejects_marker_from_unexpected_author(
        self,
    ) -> None:
        comments = (
            {
                "id": 42,
                "body": COMMENT_MARKER,
                "user": {
                    "login": "random-user",
                },
            },
        )

        with self.assertRaisesRegex(
            StickyCommentError,
            "unexpected author",
        ):
            decide_sticky_comment(
                comments,
                expected_author_login=(
                    "github-actions[bot]"
                ),
            )

    def test_rejects_empty_expected_author(self) -> None:
        with self.assertRaisesRegex(
            StickyCommentError,
            "non-empty string",
        ):
            decide_sticky_comment(
                (),
                expected_author_login=" ",
            )


if __name__ == "__main__":
    unittest.main()
