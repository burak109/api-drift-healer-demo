from __future__ import annotations

import ast
import json
import tokenize
from dataclasses import dataclass
from difflib import unified_diff
from io import StringIO
from pathlib import Path

from api_drift_healer.python_request_analyzer import (
    PythonRequestAnalysisResult,
)


class PythonDiffError(ValueError):
    """Raised when a Python patch suggestion cannot be generated safely."""


@dataclass(frozen=True, slots=True)
class PythonPatchSuggestion:
    """A suggested Python field rename that was not written to disk."""

    source_path: Path
    old_field: str
    new_field: str
    original_source: str
    suggested_source: str
    unified_diff: str


def build_python_patch_suggestion(
    result: PythonRequestAnalysisResult,
) -> PythonPatchSuggestion:
    """
    Build an in-memory Python field rename suggestion.

    The source file is never modified.
    """

    analysis = result.analysis

    if not analysis.safe_to_patch:
        raise PythonDiffError(
            "Python patch suggestion requires a SAFE_PATCH decision."
        )

    old_field = analysis.old_field
    new_field = analysis.new_field

    if old_field is None or new_field is None:
        raise PythonDiffError(
            "SAFE_PATCH result must contain old and new field names."
        )

    try:
        original_source = result.source_path.read_text(
            encoding="utf-8",
        )
    except OSError as exc:
        raise PythonDiffError(
            f"Python source could not be read: {result.source_path}"
        ) from exc

    payload = result.request.payload
    payload_end_line = (
        payload.end_line_number
        if payload.end_line_number is not None
        else payload.line_number
    )

    try:
        tokens = list(
            tokenize.generate_tokens(
                StringIO(original_source).readline
            )
        )
    except (tokenize.TokenError, IndentationError) as exc:
        raise PythonDiffError(
            "Python source could not be tokenized safely."
        ) from exc

    matching_tokens: list[tokenize.TokenInfo] = []

    for index, token in enumerate(tokens):
        if token.type != tokenize.STRING:
            continue

        token_line = token.start[0]

        if not (
            payload.line_number
            <= token_line
            <= payload_end_line
        ):
            continue

        try:
            literal_value = ast.literal_eval(token.string)
        except (ValueError, TypeError, SyntaxError):
            continue

        if literal_value != old_field:
            continue

        if not _token_is_dictionary_key(
            tokens=tokens,
            token_index=index,
        ):
            continue

        matching_tokens.append(token)

    if not matching_tokens:
        raise PythonDiffError(
            "The stale payload field could not be found safely "
            f"in the Python source: {old_field}"
        )

    if len(matching_tokens) != 1:
        raise PythonDiffError(
            "The stale payload field appears more than once "
            "inside the payload block. Automatic suggestion "
            "was rejected as ambiguous."
        )

    target_token = matching_tokens[0]

    replacement = _render_replacement_string(
        original_token=target_token.string,
        new_field=new_field,
    )

    suggested_source = _replace_token(
        source=original_source,
        token=target_token,
        replacement=replacement,
    )

    try:
        ast.parse(suggested_source)
    except SyntaxError as exc:
        raise PythonDiffError(
            "The suggested Python source is not valid syntax."
        ) from exc

    diff_text = "".join(
        unified_diff(
            original_source.splitlines(keepends=True),
            suggested_source.splitlines(keepends=True),
            fromfile=f"a/{result.source_path.name}",
            tofile=f"b/{result.source_path.name}",
        )
    )

    if not diff_text:
        raise PythonDiffError(
            "The patch suggestion did not produce a source change."
        )

    return PythonPatchSuggestion(
        source_path=result.source_path,
        old_field=old_field,
        new_field=new_field,
        original_source=original_source,
        suggested_source=suggested_source,
        unified_diff=diff_text,
    )


def _token_is_dictionary_key(
    tokens: list[tokenize.TokenInfo],
    token_index: int,
) -> bool:
    """Return True when the string token is followed by a dictionary colon."""

    ignored_token_types = {
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.COMMENT,
        tokenize.INDENT,
        tokenize.DEDENT,
    }

    next_index = token_index + 1

    while next_index < len(tokens):
        next_token = tokens[next_index]

        if next_token.type in ignored_token_types:
            next_index += 1
            continue

        return (
            next_token.type == tokenize.OP
            and next_token.string == ":"
        )

    return False


def _render_replacement_string(
    original_token: str,
    new_field: str,
) -> str:
    """Preserve simple single or double quote style."""

    if (
        original_token.startswith('"')
        and original_token.endswith('"')
    ):
        return json.dumps(new_field)

    if (
        original_token.startswith("'")
        and original_token.endswith("'")
    ):
        escaped_value = (
            new_field
            .replace("\\", "\\\\")
            .replace("'", "\\'")
        )

        return f"'{escaped_value}'"

    raise PythonDiffError(
        "Unsupported Python string style for payload field."
    )


def _replace_token(
    source: str,
    token: tokenize.TokenInfo,
    replacement: str,
) -> str:
    """Replace one same-line source token without writing to disk."""

    start_line, start_column = token.start
    end_line, end_column = token.end

    if start_line != end_line:
        raise PythonDiffError(
            "Multi-line payload field strings are not supported."
        )

    source_lines = source.splitlines(keepends=True)
    line_index = start_line - 1

    if line_index >= len(source_lines):
        raise PythonDiffError(
            "Payload field position exceeds the source length."
        )

    original_line = source_lines[line_index]

    source_lines[line_index] = (
        original_line[:start_column]
        + replacement
        + original_line[end_column:]
    )

    return "".join(source_lines)