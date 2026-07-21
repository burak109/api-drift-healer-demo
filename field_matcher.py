"""Deterministic field matching helpers for API Drift Healer."""

from __future__ import annotations

from dataclasses import dataclass
import re


SEMANTIC_ALIASES: dict[str, frozenset[str]] = {
    "email": frozenset({
        "email",
        "mail",
    }),
    "phone": frozenset({
        "phone",
        "mobile",
        "telephone",
        "tel",
    }),
    "name": frozenset({
        "name",
        "firstname",
        "lastname",
        "fullname",
        "surname",
    }),
    "id": frozenset({
        "id",
        "identifier",
        "uuid",
    }),
    "date": frozenset({
        "date",
        "time",
        "datetime",
        "timestamp",
        "created",
        "updated",
        "modified",
        "deleted",
    }),
    "address": frozenset({
        "address",
        "location",
    }),
}


# Qualifiers inside the same group must not contradict each other.
#
# Examples:
# firstName -> last_name      conflict
# createdAt -> updated_at     conflict
# primaryEmail -> secondary_email conflict
EXCLUSIVE_QUALIFIER_GROUPS: dict[str, frozenset[str]] = {
    "name_position": frozenset({
        "first",
        "last",
        "middle",
        "given",
        "family",
        "surname",
    }),
    "lifecycle": frozenset({
        "created",
        "updated",
        "modified",
        "deleted",
    }),
    "priority": frozenset({
        "primary",
        "secondary",
    }),
}


@dataclass(frozen=True)
class SemanticMatchAnalysis:
    """Explainable semantic comparison between two field names."""

    source_tokens: tuple[str, ...]
    target_tokens: tuple[str, ...]
    source_concepts: tuple[str, ...]
    target_concepts: tuple[str, ...]
    shared_concepts: tuple[str, ...]
    qualifier_conflicts: tuple[str, ...]

    @property
    def has_shared_concept(self) -> bool:
        return bool(self.shared_concepts)

    @property
    def is_semantically_safe(self) -> bool:
        return self.has_shared_concept and not self.qualifier_conflicts


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
    """Return normalized tokens as one space-separated string."""
    return " ".join(normalize_field_name(field_name))


def extract_semantic_concepts(field_name: str) -> set[str]:
    """
    Extract known semantic concepts from a field name.

    Examples:
        userEmail     -> {"email"}
        phone_number  -> {"phone"}
        userId        -> {"id"}
        createdAt     -> {"date"}
    """
    tokens = set(normalize_field_name(field_name))
    concepts: set[str] = set()

    for concept, aliases in SEMANTIC_ALIASES.items():
        if tokens.intersection(aliases):
            concepts.add(concept)

    return concepts


def find_qualifier_conflicts(
    source_field: str,
    target_field: str,
) -> list[str]:
    """
    Detect contradictory qualifiers between two field names.

    Examples:
        firstName -> last_name
        createdAt -> updated_at
        primaryEmail -> secondary_email
    """
    source_tokens = set(normalize_field_name(source_field))
    target_tokens = set(normalize_field_name(target_field))

    conflicts: list[str] = []

    for group_name, qualifiers in EXCLUSIVE_QUALIFIER_GROUPS.items():
        source_matches = source_tokens.intersection(qualifiers)
        target_matches = target_tokens.intersection(qualifiers)

        if (
            source_matches
            and target_matches
            and source_matches != target_matches
        ):
            source_value = ",".join(sorted(source_matches))
            target_value = ",".join(sorted(target_matches))

            conflicts.append(
                f"{group_name}: {source_value} -> {target_value}"
            )

    return conflicts


def analyze_semantic_match(
    source_field: str,
    target_field: str,
) -> SemanticMatchAnalysis:
    """
    Compare two field names and return explainable semantic evidence.

    This function does not calculate the final V0.4 score yet.
    """
    source_tokens = tuple(normalize_field_name(source_field))
    target_tokens = tuple(normalize_field_name(target_field))

    source_concepts = extract_semantic_concepts(source_field)
    target_concepts = extract_semantic_concepts(target_field)

    shared_concepts = source_concepts.intersection(target_concepts)

    qualifier_conflicts = find_qualifier_conflicts(
        source_field,
        target_field,
    )

    return SemanticMatchAnalysis(
        source_tokens=source_tokens,
        target_tokens=target_tokens,
        source_concepts=tuple(sorted(source_concepts)),
        target_concepts=tuple(sorted(target_concepts)),
        shared_concepts=tuple(sorted(shared_concepts)),
        qualifier_conflicts=tuple(qualifier_conflicts),
    )


# ---------------------------------------------------------------------------
# OpenAPI type and format compatibility
# ---------------------------------------------------------------------------

from datetime import datetime
from typing import Any
from uuid import UUID


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

PHONE_PATTERN = re.compile(
    r"^\+?[0-9][0-9\s().-]{6,}[0-9]$"
)


@dataclass(frozen=True)
class TypeFormatAnalysis:
    """Explainable OpenAPI type and format compatibility result."""

    expected_type: str | None
    expected_format: str | None
    detected_type: str
    detected_format: str | None
    type_compatible: bool | None
    format_compatible: bool | None
    reasons: tuple[str, ...]

    @property
    def has_conflict(self) -> bool:
        """Return True when type or format evidence rejects the match."""
        return (
            self.type_compatible is False
            or self.format_compatible is False
        )


def detect_value_type(value: Any) -> str:
    """
    Detect the JSON/OpenAPI-compatible runtime type of a Python value.

    Boolean must be checked before integer because bool is a subclass
    of int in Python. Because apparently even primitive types enjoy
    creating edge cases.
    """
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "boolean"

    if isinstance(value, int):
        return "integer"

    if isinstance(value, float):
        return "number"

    if isinstance(value, str):
        return "string"

    if isinstance(value, list):
        return "array"

    if isinstance(value, dict):
        return "object"

    return "unknown"


def _is_uuid(value: str) -> bool:
    """Return True when the complete string is a valid UUID."""
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False

    return str(parsed) == value.lower()


def _is_datetime(value: str) -> bool:
    """Return True for ISO-8601-style date-time strings."""
    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False

    # A date without a time component should not count as date-time.
    return "T" in value or " " in value


def detect_value_format(value: Any) -> str | None:
    """
    Detect a known semantic format from a runtime value.

    Supported string formats:
        email
        uuid
        date-time
        phone

    Plain strings return None.
    """
    if not isinstance(value, str):
        return None

    stripped = value.strip()

    if not stripped:
        return None

    if EMAIL_PATTERN.fullmatch(stripped):
        return "email"

    if _is_uuid(stripped):
        return "uuid"

    if _is_datetime(stripped):
        return "date-time"

    if PHONE_PATTERN.fullmatch(stripped):
        return "phone"

    return None


def is_openapi_type_compatible(
    value: Any,
    expected_type: str,
) -> bool:
    """
    Check whether a runtime value matches an OpenAPI type.

    An integer is also accepted for the broader OpenAPI number type.
    """
    detected_type = detect_value_type(value)

    compatibility_map: dict[str, set[str]] = {
        "string": {"string"},
        "integer": {"integer"},
        "number": {"integer", "number"},
        "boolean": {"boolean"},
        "array": {"array"},
        "object": {"object"},
        "null": {"null"},
    }

    allowed_types = compatibility_map.get(expected_type.lower())

    if allowed_types is None:
        return False

    return detected_type in allowed_types


def analyze_openapi_compatibility(
    value: Any,
    field_schema: dict[str, Any],
) -> TypeFormatAnalysis:
    """
    Compare a test value with an OpenAPI field schema.

    Missing type or format metadata is treated as unknown evidence,
    not as automatic rejection.
    """
    if not isinstance(field_schema, dict):
        raise TypeError("field_schema must be a dictionary")

    raw_expected_type = field_schema.get("type")
    raw_expected_format = field_schema.get("format")

    expected_type = (
        str(raw_expected_type).lower()
        if raw_expected_type is not None
        else None
    )

    expected_format = (
        str(raw_expected_format).lower()
        if raw_expected_format is not None
        else None
    )

    detected_type = detect_value_type(value)
    detected_format = detect_value_format(value)

    reasons: list[str] = []

    if expected_type is None:
        type_compatible: bool | None = None
        reasons.append("OpenAPI target type is not specified")
    else:
        type_compatible = is_openapi_type_compatible(
            value,
            expected_type,
        )

        if type_compatible:
            reasons.append(
                f"Value type '{detected_type}' matches "
                f"OpenAPI type '{expected_type}'"
            )
        else:
            reasons.append(
                f"Value type '{detected_type}' conflicts with "
                f"OpenAPI type '{expected_type}'"
            )

    if expected_format is None:
        format_compatible: bool | None = None
        reasons.append("OpenAPI target format is not specified")
    else:
        format_compatible = detected_format == expected_format

        if format_compatible:
            reasons.append(
                f"Detected value format '{detected_format}' matches "
                f"OpenAPI format '{expected_format}'"
            )
        else:
            detected_description = detected_format or "unknown/plain"

            reasons.append(
                f"Detected value format '{detected_description}' "
                f"conflicts with OpenAPI format '{expected_format}'"
            )

    return TypeFormatAnalysis(
        expected_type=expected_type,
        expected_format=expected_format,
        detected_type=detected_type,
        detected_format=detected_format,
        type_compatible=type_compatible,
        format_compatible=format_compatible,
        reasons=tuple(reasons),
    )


# ---------------------------------------------------------------------------
# Deterministic match scoring and final safety decision
# ---------------------------------------------------------------------------

from difflib import SequenceMatcher


SAFE_MATCH_THRESHOLD = 0.70

EXACT_NORMALIZED_MATCH_WEIGHT = 0.55
SHARED_SEMANTIC_CONCEPT_WEIGHT = 0.40
TYPE_COMPATIBILITY_WEIGHT = 0.15
FORMAT_COMPATIBILITY_WEIGHT = 0.20
STRING_SIMILARITY_WEIGHT = 0.05


@dataclass(frozen=True)
class FieldMatchDecision:
    """Final explainable decision for one source-target field pair."""

    source_field: str
    target_field: str
    score: float
    threshold: float
    confidence: str
    safe_to_patch: bool
    normalized_exact_match: bool
    string_similarity: float
    semantic_analysis: SemanticMatchAnalysis
    compatibility_analysis: TypeFormatAnalysis
    reasons: tuple[str, ...]


def calculate_string_similarity(
    source_field: str,
    target_field: str,
) -> float:
    """
    Calculate conservative text similarity between normalized fields.

    String similarity is intentionally a weak signal. It may support
    stronger evidence, but it must never approve a patch by itself.
    """
    source_text = normalized_field_text(source_field)
    target_text = normalized_field_text(target_field)

    if not source_text or not target_text:
        return 0.0

    return SequenceMatcher(
        None,
        source_text,
        target_text,
    ).ratio()


def evaluate_field_match(
    source_field: str,
    target_field: str,
    source_value: Any,
    target_schema: dict[str, Any],
    threshold: float = SAFE_MATCH_THRESHOLD,
) -> FieldMatchDecision:
    """
    Produce a deterministic SAFE/REJECT decision for a field rename.

    Safety rules:
    - qualifier conflicts always reject
    - OpenAPI type or format conflicts always reject
    - string similarity cannot approve a match alone
    - a strong field-name anchor is required
    - final score must meet the configured threshold

    Strong anchors:
    - normalized field names are exactly equal, or
    - fields share a semantic concept and value format matches OpenAPI
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")

    semantic_analysis = analyze_semantic_match(
        source_field,
        target_field,
    )

    compatibility_analysis = analyze_openapi_compatibility(
        source_value,
        target_schema,
    )

    source_tokens = semantic_analysis.source_tokens
    target_tokens = semantic_analysis.target_tokens

    normalized_exact_match = (
        bool(source_tokens)
        and source_tokens == target_tokens
    )

    string_similarity = calculate_string_similarity(
        source_field,
        target_field,
    )

    raw_score = 0.0
    reasons: list[str] = []

    if normalized_exact_match:
        raw_score += EXACT_NORMALIZED_MATCH_WEIGHT
        reasons.append(
            "Normalized field tokens match exactly"
        )
    else:
        reasons.append(
            "Normalized field tokens do not match exactly"
        )

    if semantic_analysis.shared_concepts:
        raw_score += SHARED_SEMANTIC_CONCEPT_WEIGHT
        shared = ", ".join(
            semantic_analysis.shared_concepts
        )
        reasons.append(
            f"Shared semantic concept: {shared}"
        )
    else:
        reasons.append(
            "No shared semantic concept was found"
        )

    if compatibility_analysis.type_compatible is True:
        raw_score += TYPE_COMPATIBILITY_WEIGHT

    if compatibility_analysis.format_compatible is True:
        raw_score += FORMAT_COMPATIBILITY_WEIGHT

    similarity_contribution = (
        string_similarity * STRING_SIMILARITY_WEIGHT
    )
    raw_score += similarity_contribution

    reasons.extend(compatibility_analysis.reasons)

    reasons.append(
        "Normalized string similarity: "
        f"{string_similarity:.3f}"
    )

    if semantic_analysis.qualifier_conflicts:
        reasons.extend(
            "Qualifier conflict: " + conflict
            for conflict in semantic_analysis.qualifier_conflicts
        )

    has_semantic_format_anchor = (
        bool(semantic_analysis.shared_concepts)
        and compatibility_analysis.format_compatible is True
    )

    has_strong_anchor = (
        normalized_exact_match
        or has_semantic_format_anchor
    )

    if not has_strong_anchor:
        reasons.append(
            "No strong matching anchor was found"
        )

    score = min(1.0, round(raw_score, 3))

    has_hard_conflict = (
        bool(semantic_analysis.qualifier_conflicts)
        or compatibility_analysis.has_conflict
    )

    safe_to_patch = (
        not has_hard_conflict
        and has_strong_anchor
        and score >= threshold
    )

    if safe_to_patch and score >= 0.75:
        confidence = "High"
    elif safe_to_patch:
        confidence = "Medium"
    else:
        confidence = "Low"

    if score < threshold:
        reasons.append(
            f"Score {score:.3f} is below "
            f"safety threshold {threshold:.3f}"
        )

    if has_hard_conflict:
        reasons.append(
            "Hard safety conflict detected"
        )

    if safe_to_patch:
        reasons.append(
            "Decision: SAFE PATCH"
        )
    else:
        reasons.append(
            "Decision: REJECT"
        )

    return FieldMatchDecision(
        source_field=source_field,
        target_field=target_field,
        score=score,
        threshold=threshold,
        confidence=confidence,
        safe_to_patch=safe_to_patch,
        normalized_exact_match=normalized_exact_match,
        string_similarity=round(string_similarity, 3),
        semantic_analysis=semantic_analysis,
        compatibility_analysis=compatibility_analysis,
        reasons=tuple(reasons),
    )
