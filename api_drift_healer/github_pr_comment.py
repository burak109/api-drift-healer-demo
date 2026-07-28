"""Decide whether a sticky pull request comment should be created or updated."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from api_drift_healer.github_pr_report import COMMENT_MARKER


class StickyCommentError(ValueError):
    """Raised when sticky comment state is unsafe or ambiguous."""


class StickyCommentAction(str, Enum):
    """Supported sticky comment operations."""

    CREATE = "create"
    UPDATE = "update"


@dataclass(frozen=True, slots=True)
class StickyCommentDecision:
    """Deterministic sticky comment operation."""

    action: StickyCommentAction
    comment_id: int | None


def _validate_marker(marker: str) -> str:
    """Validate and normalize the sticky comment marker."""

    if not isinstance(marker, str):
        raise StickyCommentError(
            "Comment marker must be a string."
        )

    normalized_marker = marker.strip()

    if not normalized_marker:
        raise StickyCommentError(
            "Comment marker cannot be empty."
        )

    return normalized_marker


def _comment_body(
    comment: Mapping[str, Any],
    index: int,
) -> str:
    """Return one GitHub comment body safely."""

    body = comment.get(
        "body",
        "",
    )

    if body is None:
        return ""

    if not isinstance(body, str):
        raise StickyCommentError(
            "Comment body must be a string "
            f"at index {index}."
        )

    return body


def _comment_id(
    comment: Mapping[str, Any],
    index: int,
) -> int:
    """Return one positive GitHub comment identifier."""

    value = comment.get("id")

    if type(value) is not int or value <= 0:
        raise StickyCommentError(
            "Marker comment must have a positive "
            f"integer id at index {index}."
        )

    return value


def _comment_author_login(
    comment: Mapping[str, Any],
    index: int,
) -> str | None:
    """Return the GitHub login for one comment author."""

    user = comment.get("user")

    if user is None:
        return None

    if not isinstance(user, Mapping):
        raise StickyCommentError(
            "Comment user must be an object "
            f"at index {index}."
        )

    login = user.get("login")

    if login is None:
        return None

    if not isinstance(login, str):
        raise StickyCommentError(
            "Comment user login must be a string "
            f"at index {index}."
        )

    return login


def decide_sticky_comment(
    comments: Iterable[Mapping[str, Any]],
    *,
    marker: str = COMMENT_MARKER,
    expected_author_login: str | None = None,
) -> StickyCommentDecision:
    """Choose CREATE or UPDATE for one sticky PR comment.

    A marker owned by an unexpected author is rejected instead
    of being updated or silently ignored.
    """

    normalized_marker = _validate_marker(marker)

    if (
        expected_author_login is not None
        and (
            not isinstance(expected_author_login, str)
            or not expected_author_login.strip()
        )
    ):
        raise StickyCommentError(
            "Expected author login must be a "
            "non-empty string."
        )

    normalized_author = (
        expected_author_login.strip()
        if expected_author_login is not None
        else None
    )

    matching_comment_ids: list[int] = []

    for index, comment in enumerate(comments):
        if not isinstance(comment, Mapping):
            raise StickyCommentError(
                "Each comment must be an object "
                f"at index {index}."
            )

        body = _comment_body(
            comment,
            index,
        )
        marker_count = body.count(
            normalized_marker
        )

        if marker_count == 0:
            continue

        if marker_count > 1:
            raise StickyCommentError(
                "Marker appears more than once "
                f"in comment at index {index}."
            )

        author_login = _comment_author_login(
            comment,
            index,
        )

        if (
            normalized_author is not None
            and author_login != normalized_author
        ):
            raise StickyCommentError(
                "Marker comment belongs to an "
                "unexpected author."
            )

        matching_comment_ids.append(
            _comment_id(
                comment,
                index,
            )
        )

    if len(matching_comment_ids) > 1:
        raise StickyCommentError(
            "Multiple sticky marker comments were found."
        )

    if not matching_comment_ids:
        return StickyCommentDecision(
            action=StickyCommentAction.CREATE,
            comment_id=None,
        )

    return StickyCommentDecision(
        action=StickyCommentAction.UPDATE,
        comment_id=matching_comment_ids[0],
    )
