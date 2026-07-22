import json
import re
from pathlib import Path
from urllib.parse import urlparse

from api_drift_healer.models import (
    NormalizedRequest,
    ParsedHttpRequest,
)


class HttpFileParseError(ValueError):
    """Raised when a .http request cannot be parsed safely."""


_REQUEST_LINE = re.compile(
    r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)"
    r"(?:\s+HTTP/\d(?:\.\d)?)?$",
    re.IGNORECASE,
)


def parse_http_file(
    file_path: str | Path,
) -> ParsedHttpRequest:
    path = Path(file_path)

    with path.open(
    "r",
    encoding="utf-8",
    newline="",
) as file:
     source_text = file.read()

    return parse_http_request(
        source_text,
        name=path.stem,
    )


def parse_http_request(
    source_text: str,
    *,
    name: str = "http-request",
) -> ParsedHttpRequest:
    if not source_text.strip():
        raise HttpFileParseError(
            "HTTP file is empty."
        )

    newline = (
        "\r\n"
        if "\r\n" in source_text
        else "\n"
    )

    if source_text.count("###") > 1:
        raise HttpFileParseError(
            "Multiple requests detected. "
            "V1.1 supports one request per .http file."
        )

    lines = source_text.splitlines(
        keepends=True
    )

    request_line_index = None
    request_match = None
    offset = 0

    for index, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            offset += len(line)
            continue

        if stripped.startswith("#"):
            offset += len(line)
            continue

        request_match = _REQUEST_LINE.match(
            stripped
        )

        if request_match:
            request_line_index = index
            break

        raise HttpFileParseError(
            "Valid HTTP request line was not found."
        )

    if request_line_index is None:
        raise HttpFileParseError(
            "Valid HTTP request line was not found."
        )

    method = request_match.group(1).upper()
    raw_url = request_match.group(2)

    body_start = _find_body_start(
        lines,
        request_line_index,
    )

    body_end = len(source_text.rstrip())

    if body_start >= body_end:
        raise HttpFileParseError(
            "HTTP request body is missing."
        )

    body_text = source_text[
        body_start:body_end
    ]

    try:
        body = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise HttpFileParseError(
            f"HTTP request body is not valid JSON: {exc.msg}"
        ) from exc

    if not isinstance(body, dict):
        raise HttpFileParseError(
            "HTTP request body must be a JSON object."
        )

    request = NormalizedRequest(
        name=name,
        method=method,
        path=_extract_path(raw_url),
        body=body,
    )

    return ParsedHttpRequest(
        request=request,
        source_text=source_text,
        body_start=body_start,
        body_end=body_end,
        newline=newline,
    )


def _find_body_start(
    lines: list[str],
    request_line_index: int,
) -> int:
    offset = sum(
        len(line)
        for line in lines[
            : request_line_index + 1
        ]
    )

    for line in lines[
        request_line_index + 1 :
    ]:
        offset += len(line)

        if not line.strip():
            return offset

    raise HttpFileParseError(
        "Blank line before HTTP body is missing."
    )


def _extract_path(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    path = parsed.path

    if not path and raw_url.startswith("/"):
        path = raw_url.split("?", 1)[0]

    if not path:
        raise HttpFileParseError(
            "HTTP request URL does not contain a path."
        )

    return path
class HttpFilePatchError(ValueError):
    """Raised when an HTTP request cannot be patched safely."""


def patch_http_request_body(
    parsed_request: ParsedHttpRequest,
    old_field: str,
    new_field: str,
) -> str:
    """Rename one top-level JSON field without reformatting the file."""

    old_field = old_field.strip()
    new_field = new_field.strip()

    if not old_field or not new_field:
        raise HttpFilePatchError(
            "Patch field names cannot be empty."
        )

    if old_field == new_field:
        raise HttpFilePatchError(
            "Old and new field names must be different."
        )

    body = parsed_request.request.body

    if old_field not in body:
        raise HttpFilePatchError(
            f"Field '{old_field}' was not found "
            "in the top-level HTTP request body."
        )

    if new_field in body:
        raise HttpFilePatchError(
            f"Field '{new_field}' already exists "
            "in the HTTP request body."
        )

    matches = _find_top_level_key_spans(
        parsed_request.body_text,
        old_field,
    )

    if len(matches) != 1:
        raise HttpFilePatchError(
            f"Expected exactly one top-level key "
            f"named '{old_field}', found {len(matches)}."
        )

    key_start, key_end = matches[0]

    replacement = json.dumps(
        new_field,
        ensure_ascii=False,
    )

    patched_body = (
        parsed_request.body_text[:key_start]
        + replacement
        + parsed_request.body_text[key_end:]
    )

    patched_source = (
        parsed_request.source_text[
            : parsed_request.body_start
        ]
        + patched_body
        + parsed_request.source_text[
            parsed_request.body_end :
        ]
    )

    try:
        validated = parse_http_request(
            patched_source,
            name=parsed_request.request.name,
        )
    except HttpFileParseError as exc:
        raise HttpFilePatchError(
            "Patched HTTP request is not valid."
        ) from exc

    if new_field not in validated.request.body:
        raise HttpFilePatchError(
            "Patched field was not found after validation."
        )

    return patched_source


def _find_top_level_key_spans(
    body_text: str,
    target_field: str,
) -> list[tuple[int, int]]:
    matches: list[tuple[int, int]] = []

    depth = 0
    index = 0

    while index < len(body_text):
        character = body_text[index]

        if character == '"':
            token_start = index
            token_end = _find_json_string_end(
                body_text,
                token_start,
            )

            if depth == 1:
                next_index = token_end

                while (
                    next_index < len(body_text)
                    and body_text[next_index].isspace()
                ):
                    next_index += 1

                if (
                    next_index < len(body_text)
                    and body_text[next_index] == ":"
                ):
                    decoded_key = json.loads(
                        body_text[token_start:token_end]
                    )

                    if decoded_key == target_field:
                        matches.append(
                            (token_start, token_end)
                        )

            index = token_end
            continue

        if character in "{[":
            depth += 1
        elif character in "}]":
            depth -= 1

        index += 1

    return matches


def _find_json_string_end(
    text: str,
    start: int,
) -> int:
    index = start + 1

    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue

        if text[index] == '"':
            return index + 1

        index += 1

    raise HttpFilePatchError(
        "Unterminated JSON string was found."
    )