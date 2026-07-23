from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from api_drift_healer.drift_analyzer import analyze_request_drift
from api_drift_healer.models import (
    DriftAnalysisResult,
    NormalizedRequest,
)
from api_drift_healer.openapi_resolver import (
    resolve_request_schema_file,
)
from api_drift_healer.python_parser import (
    PythonParseError,
    PythonRequest,
    parse_python_file,
)


class PythonRequestAnalysisError(ValueError):
    """Raised when a Python request cannot be analyzed safely."""


@dataclass(frozen=True, slots=True)
class PythonRequestAnalysisResult:
    """Static drift analysis result for one Python requests call."""

    source_path: Path
    request: PythonRequest
    normalized_request: NormalizedRequest
    analysis: DriftAnalysisResult


def extract_request_path(url: str) -> str:
    """Extract an OpenAPI-compatible path from a literal request URL."""

    normalized_url = url.strip()

    if not normalized_url:
        raise PythonRequestAnalysisError(
            "Request URL cannot be empty."
        )

    parsed = urlsplit(normalized_url)

    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        raise PythonRequestAnalysisError(
            f"Unsupported request URL scheme: {parsed.scheme}"
        )

    path = parsed.path.strip()

    if not path:
        raise PythonRequestAnalysisError(
            f"Request URL does not contain a path: {url}"
        )

    if not path.startswith("/"):
        path = f"/{path}"

    return path


def analyze_python_request_file(
    python_path: str | Path,
    openapi_path: str | Path,
) -> PythonRequestAnalysisResult:
    """
    Analyze one literal requests call without changing the Python file.

    V1.3 initially supports exactly one requests.post, requests.put,
    or requests.patch call per analyzed Python file.
    """

    source_path = Path(
        python_path
    ).expanduser().resolve()

    try:
        parsed = parse_python_file(source_path)
    except PythonParseError as exc:
        raise PythonRequestAnalysisError(str(exc)) from exc

    if not parsed.requests:
        skipped_details = "; ".join(parsed.skipped_reasons)

        message = (
            "No supported requests.post, requests.put, or "
            "requests.patch call was found."
        )

        if skipped_details:
            message = f"{message} {skipped_details}"

        raise PythonRequestAnalysisError(message)

    if len(parsed.requests) != 1:
        raise PythonRequestAnalysisError(
            "V1.3 supports exactly one request call per Python file. "
            f"Found: {len(parsed.requests)}"
        )

    request = parsed.requests[0]
    request_path = extract_request_path(request.url)

    normalized_request = NormalizedRequest(
        name=f"{source_path.name}:{request.line_number}",
        method=request.method,
        path=request_path,
        body=request.payload.values,
    )

    schema = resolve_request_schema_file(
        openapi_path=openapi_path,
        method=normalized_request.method,
        path=normalized_request.path,
    )

    analysis = analyze_request_drift(
        request=normalized_request,
        schema=schema,
    )

    return PythonRequestAnalysisResult(
        source_path=source_path,
        request=request,
        normalized_request=normalized_request,
        analysis=analysis,
    )