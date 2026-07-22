from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class NormalizedRequest:
    """Format-independent API request used by the core drift engine."""

    name: str
    method: str
    path: str
    body: dict[str, Any]

    def __post_init__(self) -> None:
        name = self.name.strip()
        method = self.method.strip().upper()
        path = self.path.strip()

        if not name:
            raise ValueError("Request name cannot be empty.")

        if not method:
            raise ValueError("Request method cannot be empty.")

        if not path:
            raise ValueError("Request path cannot be empty.")

        if not isinstance(self.body, dict):
            raise TypeError("Request body must be a dictionary.")

        if not path.startswith("/"):
            path = f"/{path}"

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "body", dict(self.body))


@dataclass(frozen=True, slots=True)
class ResolvedRequestSchema:
    """Resolved OpenAPI request schema for one method and path."""

    path: str
    method: str
    required_fields: tuple[str, ...]
    properties: dict[str, dict[str, Any]]

    def __post_init__(self) -> None:
        method = self.method.strip().upper()
        path = self.path.strip()

        if not method:
            raise ValueError("Schema method cannot be empty.")

        if not path:
            raise ValueError("Schema path cannot be empty.")

        if not path.startswith("/"):
            path = f"/{path}"

        if not isinstance(self.required_fields, tuple):
            raise TypeError("Required fields must be a tuple.")

        if not all(
            isinstance(field, str) and field.strip()
            for field in self.required_fields
        ):
            raise ValueError(
                "Required fields must contain non-empty strings."
            )

        if not isinstance(self.properties, dict):
            raise TypeError("Schema properties must be a dictionary.")

        copied_properties: dict[str, dict[str, Any]] = {}

        for field_name, field_schema in self.properties.items():
            if not isinstance(field_name, str) or not field_name.strip():
                raise ValueError(
                    "Property names must be non-empty strings."
                )

            if not isinstance(field_schema, dict):
                raise TypeError(
                    f"Schema for property '{field_name}' "
                    "must be a dictionary."
                )

            copied_properties[field_name] = dict(field_schema)

        missing_property_schemas = [
            field
            for field in self.required_fields
            if field not in copied_properties
        ]

        if missing_property_schemas:
            raise ValueError(
                "Required fields must also exist in properties: "
                + ", ".join(missing_property_schemas)
            )

        object.__setattr__(self, "method", method)
        object.__setattr__(self, "path", path)
        object.__setattr__(
            self,
            "required_fields",
            tuple(self.required_fields),
        )
        object.__setattr__(
            self,
            "properties",
            copied_properties,
        )



DriftDecision = Literal[
    "NO_DRIFT",
    "SAFE_PATCH",
    "REJECTED",
    "COMPLEX_DRIFT",
]


@dataclass(frozen=True, slots=True)
class DriftAnalysisResult:
    """Format-independent result produced by the drift analyzer."""

    decision: DriftDecision
    request_name: str
    missing_required_fields: tuple[str, ...]
    invalid_existing_fields: tuple[str, ...]
    old_field: str | None = None
    new_field: str | None = None
    score: float | None = None
    threshold: float | None = None
    confidence: str | None = None
    reasons: tuple[str, ...] = ()

    @property
    def safe_to_patch(self) -> bool:
        return self.decision == "SAFE_PATCH"



@dataclass(frozen=True, slots=True)
class ParsedHttpRequest:
    """Parsed .http request with source positions for safe patching."""

    request: NormalizedRequest
    source_text: str
    body_start: int
    body_end: int
    newline: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, NormalizedRequest):
            raise TypeError(
                "Parsed HTTP request must contain a NormalizedRequest."
            )

        if not isinstance(self.source_text, str):
            raise TypeError("HTTP source text must be a string.")

        if not isinstance(self.body_start, int):
            raise TypeError("HTTP body start must be an integer.")

        if not isinstance(self.body_end, int):
            raise TypeError("HTTP body end must be an integer.")

        if self.body_start < 0:
            raise ValueError("HTTP body start cannot be negative.")

        if self.body_end < self.body_start:
            raise ValueError(
                "HTTP body end cannot be before body start."
            )

        if self.body_end > len(self.source_text):
            raise ValueError(
                "HTTP body end cannot exceed source length."
            )

        if self.newline not in {"\n", "\r\n"}:
            raise ValueError(
                "HTTP newline must be LF or CRLF."
            )

    @property
    def body_text(self) -> str:
        """Return the original body text without changing formatting."""

        return self.source_text[
            self.body_start:self.body_end
        ]
