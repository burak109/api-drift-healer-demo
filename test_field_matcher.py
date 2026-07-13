import unittest

from field_matcher import (
    analyze_semantic_match,
    extract_semantic_concepts,
    normalize_field_name,
    normalized_field_text,
)


class NormalizeFieldNameTests(unittest.TestCase):
    def test_camel_case(self) -> None:
        self.assertEqual(
            normalize_field_name("userEmail"),
            ["user", "email"],
        )

    def test_snake_case(self) -> None:
        self.assertEqual(
            normalize_field_name("email_address"),
            ["email", "address"],
        )

    def test_kebab_case(self) -> None:
        self.assertEqual(
            normalize_field_name("phone-number"),
            ["phone", "number"],
        )

    def test_pascal_case(self) -> None:
        self.assertEqual(
            normalize_field_name("FirstName"),
            ["first", "name"],
        )

    def test_identifier_acronym(self) -> None:
        self.assertEqual(
            normalize_field_name("userID"),
            ["user", "id"],
        )

    def test_long_acronym(self) -> None:
        self.assertEqual(
            normalize_field_name("HTTPStatusCode"),
            ["http", "status", "code"],
        )

    def test_created_at(self) -> None:
        self.assertEqual(
            normalize_field_name("createdAt"),
            ["created", "at"],
        )

    def test_whitespace_is_removed(self) -> None:
        self.assertEqual(
            normalize_field_name("  last_name  "),
            ["last", "name"],
        )

    def test_empty_value(self) -> None:
        self.assertEqual(normalize_field_name(""), [])

    def test_invalid_type(self) -> None:
        with self.assertRaises(TypeError):
            normalize_field_name(None)  # type: ignore[arg-type]

    def test_normalized_field_text(self) -> None:
        self.assertEqual(
            normalized_field_text("phoneNumber"),
            "phone number",
        )


class SemanticConceptTests(unittest.TestCase):
    def test_email_concept(self) -> None:
        self.assertEqual(
            extract_semantic_concepts("userEmail"),
            {"email"},
        )

    def test_phone_concept(self) -> None:
        self.assertEqual(
            extract_semantic_concepts("mobile_number"),
            {"phone"},
        )

    def test_id_concept(self) -> None:
        self.assertEqual(
            extract_semantic_concepts("userIdentifier"),
            {"id"},
        )

    def test_date_concept(self) -> None:
        self.assertEqual(
            extract_semantic_concepts("createdAt"),
            {"date"},
        )

    def test_unknown_field_has_no_known_concept(self) -> None:
        self.assertEqual(
            extract_semantic_concepts("randomValue"),
            set(),
        )


class SemanticMatchAnalysisTests(unittest.TestCase):
    def test_user_email_to_email_address_is_safe(self) -> None:
        result = analyze_semantic_match(
            "userEmail",
            "email_address",
        )

        self.assertEqual(result.shared_concepts, ("email",))
        self.assertEqual(result.qualifier_conflicts, ())
        self.assertTrue(result.is_semantically_safe)

    def test_phone_number_is_safe(self) -> None:
        result = analyze_semantic_match(
            "phoneNumber",
            "phone_number",
        )

        self.assertEqual(result.shared_concepts, ("phone",))
        self.assertTrue(result.is_semantically_safe)

    def test_first_name_to_first_name_is_safe(self) -> None:
        result = analyze_semantic_match(
            "firstName",
            "first_name",
        )

        self.assertEqual(result.shared_concepts, ("name",))
        self.assertEqual(result.qualifier_conflicts, ())
        self.assertTrue(result.is_semantically_safe)

    def test_first_name_to_last_name_is_rejected(self) -> None:
        result = analyze_semantic_match(
            "firstName",
            "last_name",
        )

        self.assertEqual(result.shared_concepts, ("name",))
        self.assertTrue(result.qualifier_conflicts)
        self.assertFalse(result.is_semantically_safe)

    def test_name_to_email_address_is_rejected(self) -> None:
        result = analyze_semantic_match(
            "name",
            "email_address",
        )

        self.assertEqual(result.shared_concepts, ())
        self.assertFalse(result.is_semantically_safe)

    def test_created_to_updated_is_rejected(self) -> None:
        result = analyze_semantic_match(
            "createdAt",
            "updated_at",
        )

        self.assertEqual(result.shared_concepts, ("date",))
        self.assertTrue(result.qualifier_conflicts)
        self.assertFalse(result.is_semantically_safe)

    def test_primary_to_secondary_email_is_rejected(self) -> None:
        result = analyze_semantic_match(
            "primaryEmail",
            "secondary_email",
        )

        self.assertEqual(result.shared_concepts, ("email",))
        self.assertTrue(result.qualifier_conflicts)
        self.assertFalse(result.is_semantically_safe)


if __name__ == "__main__":
    unittest.main()
