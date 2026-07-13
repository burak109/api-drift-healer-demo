"""Deterministic field matching helpers for API Drift Healer V0.4."""

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
