"""Deterministic field-name matching helpers for API Drift Healer V0.4."""

from __future__ import annotations

import re


def normalize_field_name(field_name: str) -> list[str]:
    """
    Convert a field name into lowercase semantic tokens.

    Supported examples:
        userEmail      -> ["user", "email"]
        email_address  -> ["email", "address"]
        phone-number   -> ["phone", "number"]
        UserID         -> ["user", "id"]
        HTTPStatusCode -> ["http", "status", "code"]

    The function is deterministic and does not guess semantic meaning.
    It only separates naming styles into comparable tokens.
    """
    if not isinstance(field_name, str):
        raise TypeError("field_name must be a string")

    value = field_name.strip()

    if not value:
        return []

    # Separate acronym-to-word transitions:
    # HTTPStatus -> HTTP Status
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)

    # Separate lowercase/digit-to-uppercase transitions:
    # userEmail -> user Email
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)

    # Treat common separators as token boundaries.
    value = re.sub(r"[_\-.]+", " ", value)

    # Remove unsupported characters without merging surrounding words.
    value = re.sub(r"[^A-Za-z0-9\s]+", " ", value)

    return [token.lower() for token in value.split() if token]


def normalized_field_text(field_name: str) -> str:
    """Return normalized field tokens as a single space-separated string."""
    return " ".join(normalize_field_name(field_name))
