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