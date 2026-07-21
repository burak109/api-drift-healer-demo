from __future__ import annotations

from copy import deepcopy

import json
import re
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from api_drift_healer.models import NormalizedRequest


class PostmanAdapterError(ValueError):
    """Raised when a Postman collection cannot be normalized safely."""


def load_postman_collection(path: str | Path) -> dict[str, Any]:
    """Load a Postman collection JSON file."""

    collection_path = Path(path)

    try:
        raw_text = collection_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise PostmanAdapterError(
            f"Could not read Postman collection: {collection_path}"
        ) from exc

    try:
        collection = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PostmanAdapterError(
            f"Postman collection is not valid JSON: {collection_path}"
        ) from exc

    if not isinstance(collection, dict):
        raise PostmanAdapterError(
            "Postman collection root must be a JSON object."
        )

    _validate_collection_version(collection)

    return collection


def normalize_postman_request_file(
    collection_path: str | Path,
    request_name: str,
) -> NormalizedRequest:
    """Load a collection and normalize one request by exact name."""

    collection = load_postman_collection(collection_path)

    return normalize_postman_request(
        collection=collection,
        request_name=request_name,
    )


def normalize_postman_request(
    collection: dict[str, Any],
    request_name: str,
) -> NormalizedRequest:
    """Convert one Postman request into a format-independent request."""

    if not isinstance(collection, dict):
        raise PostmanAdapterError(
            "Postman collection root must be a JSON object."
        )

    _validate_collection_version(collection)

    item = _find_request_item(
        collection=collection,
        request_name=request_name,
    )

    request = item.get("request")

    if not isinstance(request, dict):
        raise PostmanAdapterError(
            f"Postman item '{request_name}' does not contain a valid request."
        )

    method = request.get("method")

    if not isinstance(method, str) or not method.strip():
        raise PostmanAdapterError(
            f"Postman request '{request_name}' has no valid HTTP method."
        )

    path = _extract_request_path(
        url_value=request.get("url"),
        request_name=request_name,
    )

    body = _extract_json_body(
        request=request,
        request_name=request_name,
    )

    return NormalizedRequest(
        name=request_name,
        method=method,
        path=path,
        body=body,
    )


def _validate_collection_version(
    collection: dict[str, Any],
) -> None:
    info = collection.get("info")

    if info is None:
        return

    if not isinstance(info, dict):
        raise PostmanAdapterError(
            "Postman collection 'info' must be a JSON object."
        )

    schema = info.get("schema")

    if schema is None:
        return

    if not isinstance(schema, str):
        raise PostmanAdapterError(
            "Postman collection schema must be a string."
        )

    if "v2.1.0" not in schema:
        raise PostmanAdapterError(
            "Only Postman Collection v2.1 is currently supported."
        )


def _find_request_item(
    collection: dict[str, Any],
    request_name: str,
) -> dict[str, Any]:
    target_name = request_name.strip()

    if not target_name:
        raise PostmanAdapterError(
            "Postman request name cannot be empty."
        )

    items = collection.get("item")

    if not isinstance(items, list):
        raise PostmanAdapterError(
            "Postman collection must contain an 'item' list."
        )

    matches = [
        item
        for item in _walk_request_items(items)
        if item.get("name") == target_name
    ]

    if not matches:
        raise PostmanAdapterError(
            f"Postman request not found: {target_name}"
        )

    if len(matches) > 1:
        raise PostmanAdapterError(
            f"Multiple Postman requests share the name: {target_name}"
        )

    return matches[0]


def _walk_request_items(
    items: list[Any],
) -> Iterator[dict[str, Any]]:
    for item in items:
        if not isinstance(item, dict):
            raise PostmanAdapterError(
                "Every Postman collection item must be a JSON object."
            )

        if "request" in item:
            yield item

        nested_items = item.get("item")

        if nested_items is None:
            continue

        if not isinstance(nested_items, list):
            raise PostmanAdapterError(
                "Nested Postman folder items must be a list."
            )

        yield from _walk_request_items(nested_items)


def _extract_request_path(
    url_value: Any,
    request_name: str,
) -> str:
    if isinstance(url_value, dict):
        path_value = url_value.get("path")

        if isinstance(path_value, list):
            segments = [
                _extract_path_segment(segment)
                for segment in path_value
            ]

            return "/" + "/".join(
                segment.strip("/")
                for segment in segments
                if segment.strip("/")
            )

        raw_value = url_value.get("raw")

        if isinstance(raw_value, str):
            return _extract_path_from_raw_url(raw_value)

    if isinstance(url_value, str):
        return _extract_path_from_raw_url(url_value)

    raise PostmanAdapterError(
        f"Postman request '{request_name}' has no supported URL."
    )


def _extract_path_segment(segment: Any) -> str:
    if isinstance(segment, str):
        return segment

    if isinstance(segment, dict):
        value = segment.get("value")

        if isinstance(value, str):
            return value

    raise PostmanAdapterError(
        "Postman URL path segments must be strings or value objects."
    )


def _extract_path_from_raw_url(raw_url: str) -> str:
    cleaned_url = raw_url.strip()

    if not cleaned_url:
        raise PostmanAdapterError(
            "Postman request URL cannot be empty."
        )

    cleaned_url = cleaned_url.split("#", 1)[0]
    cleaned_url = cleaned_url.split("?", 1)[0]

    if "://" in cleaned_url:
        path = urlsplit(cleaned_url).path
    else:
        path = re.sub(
            r"^\{\{[^{}]+\}\}",
            "",
            cleaned_url,
            count=1,
        )

        if not path.startswith("/"):
            if "/" in path:
                path = "/" + path.split("/", 1)[1]
            else:
                path = "/" + path

    return path or "/"


def _extract_json_body(
    request: dict[str, Any],
    request_name: str,
) -> dict[str, Any]:
    body = request.get("body")

    if not isinstance(body, dict):
        raise PostmanAdapterError(
            f"Postman request '{request_name}' has no request body."
        )

    mode = body.get("mode")

    if mode != "raw":
        raise PostmanAdapterError(
            "Only Postman raw JSON request bodies are currently supported."
        )

    raw_body = body.get("raw")

    if not isinstance(raw_body, str):
        raise PostmanAdapterError(
            f"Postman request '{request_name}' has no valid raw body."
        )

    try:
        parsed_body = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise PostmanAdapterError(
            f"Postman request '{request_name}' raw body is not valid JSON."
        ) from exc

    if not isinstance(parsed_body, dict):
        raise PostmanAdapterError(
            "Postman raw JSON body must contain a JSON object."
        )

    return parsed_body



def patch_postman_request_body(
    collection: dict[str, Any],
    request_name: str,
    old_field: str,
    new_field: str,
) -> dict[str, Any]:
    """Return a copied collection with one safely renamed body field."""

    old_field = old_field.strip()
    new_field = new_field.strip()

    if not old_field or not new_field:
        raise PostmanAdapterError(
            "Patch field names cannot be empty."
        )

    if old_field == new_field:
        raise PostmanAdapterError(
            "Old and new field names must be different."
        )

    patched_collection = deepcopy(collection)
    _validate_collection_version(patched_collection)

    item = _find_request_item(
        collection=patched_collection,
        request_name=request_name,
    )

    request = item.get("request")

    if not isinstance(request, dict):
        raise PostmanAdapterError(
            f"Postman item '{request_name}' has no valid request."
        )

    parsed_body = _extract_json_body(
        request=request,
        request_name=request_name,
    )

    if old_field not in parsed_body:
        raise PostmanAdapterError(
            f"Field '{old_field}' was not found in request "
            f"'{request_name}'."
        )

    if new_field in parsed_body:
        raise PostmanAdapterError(
            f"Field '{new_field}' already exists in request "
            f"'{request_name}'."
        )

    patched_body = {
        new_field if field == old_field else field: value
        for field, value in parsed_body.items()
    }

    body_container = request.get("body")

    if not isinstance(body_container, dict):
        raise PostmanAdapterError(
            f"Postman request '{request_name}' has no valid body."
        )

    body_container["raw"] = json.dumps(
        patched_body,
        ensure_ascii=False,
        indent=2,
    )

    return patched_collection
