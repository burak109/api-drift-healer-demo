from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
