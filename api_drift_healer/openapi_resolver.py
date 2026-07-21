from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from api_drift_healer.models import ResolvedRequestSchema


class OpenApiResolverError(ValueError):
    """Raised when an OpenAPI request schema cannot be resolved safely."""


def load_openapi_document(
    path: str | Path,
) -> dict[str, Any]:
    """Load an OpenAPI YAML or JSON document."""

    openapi_path = Path(path)

    try:
        raw_text = openapi_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise OpenApiResolverError(
            f"Could not read OpenAPI document: {openapi_path}"
        ) from exc

    try:
        document = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise OpenApiResolverError(
            f"OpenAPI document is not valid YAML or JSON: "
            f"{openapi_path}"
        ) from exc

    if not isinstance(document, dict):
        raise OpenApiResolverError(
            "OpenAPI document root must be an object."
        )

    return document


def resolve_request_schema_file(
    openapi_path: str | Path,
    method: str,
    path: str,
) -> ResolvedRequestSchema:
    """Load an OpenAPI document and resolve one request schema."""

    document = load_openapi_document(openapi_path)

    return resolve_request_schema(
        document=document,
        method=method,
        path=path,
    )


def resolve_request_schema(
    document: dict[str, Any],
    method: str,
    path: str,
) -> ResolvedRequestSchema:
    """Resolve an inline application/json schema by exact path and method."""

    if not isinstance(document, dict):
        raise OpenApiResolverError(
            "OpenAPI document root must be an object."
        )

    normalized_method = method.strip().upper()
    normalized_path = path.strip()

    if not normalized_method:
        raise OpenApiResolverError(
            "HTTP method cannot be empty."
        )

    if not normalized_path:
        raise OpenApiResolverError(
            "Request path cannot be empty."
        )

    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"

    paths = document.get("paths")

    if not isinstance(paths, dict):
        raise OpenApiResolverError(
            "OpenAPI document must contain a 'paths' object."
        )

    path_item = paths.get(normalized_path)

    if not isinstance(path_item, dict):
        raise OpenApiResolverError(
            f"OpenAPI path not found: {normalized_path}"
        )

    operation = path_item.get(normalized_method.lower())

    if not isinstance(operation, dict):
        raise OpenApiResolverError(
            f"OpenAPI operation not found: "
            f"{normalized_method} {normalized_path}"
        )

    request_body = operation.get("requestBody")

    if not isinstance(request_body, dict):
        raise OpenApiResolverError(
            f"OpenAPI operation has no request body: "
            f"{normalized_method} {normalized_path}"
        )

    if "$ref" in request_body:
        raise OpenApiResolverError(
            "Referenced OpenAPI request bodies are not supported yet."
        )

    content = request_body.get("content")

    if not isinstance(content, dict):
        raise OpenApiResolverError(
            "OpenAPI request body must contain a content object."
        )

    json_media_type = content.get("application/json")

    if not isinstance(json_media_type, dict):
        raise OpenApiResolverError(
            "OpenAPI request body must define application/json."
        )

    schema = json_media_type.get("schema")

    if not isinstance(schema, dict):
        raise OpenApiResolverError(
            "OpenAPI application/json body must contain a schema."
        )

    if "$ref" in schema:
        raise OpenApiResolverError(
            "Referenced OpenAPI schemas are not supported yet."
        )

    if any(
        keyword in schema
        for keyword in ("allOf", "oneOf", "anyOf")
    ):
        raise OpenApiResolverError(
            "Composed OpenAPI schemas are not supported yet."
        )

    schema_type = schema.get("type")

    if schema_type is not None and schema_type != "object":
        raise OpenApiResolverError(
            "OpenAPI request schema must describe an object."
        )

    required_fields = schema.get("required", [])

    if not isinstance(required_fields, list):
        raise OpenApiResolverError(
            "OpenAPI schema 'required' must be a list."
        )

    if not all(
        isinstance(field, str) and field.strip()
        for field in required_fields
    ):
        raise OpenApiResolverError(
            "OpenAPI required fields must be non-empty strings."
        )

    properties = schema.get("properties")

    if not isinstance(properties, dict):
        raise OpenApiResolverError(
            "OpenAPI request schema must contain properties."
        )

    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str) or not field_name.strip():
            raise OpenApiResolverError(
                "OpenAPI property names must be non-empty strings."
            )

        if not isinstance(field_schema, dict):
            raise OpenApiResolverError(
                f"OpenAPI schema for property '{field_name}' "
                "must be an object."
            )

    missing_property_schemas = [
        field
        for field in required_fields
        if field not in properties
    ]

    if missing_property_schemas:
        raise OpenApiResolverError(
            "Required fields are missing from properties: "
            + ", ".join(missing_property_schemas)
        )

    return ResolvedRequestSchema(
        path=normalized_path,
        method=normalized_method,
        required_fields=tuple(required_fields),
        properties={
            field_name: dict(field_schema)
            for field_name, field_schema in properties.items()
        },
    )
