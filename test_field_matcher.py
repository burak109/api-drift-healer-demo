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


class ValueDetectionTests(unittest.TestCase):
    def test_detects_string_type(self) -> None:
        from field_matcher import detect_value_type

        self.assertEqual(
            detect_value_type("qa_user@example.com"),
            "string",
        )

    def test_detects_integer_type(self) -> None:
        from field_matcher import detect_value_type

        self.assertEqual(detect_value_type(42), "integer")

    def test_detects_number_type(self) -> None:
        from field_matcher import detect_value_type

        self.assertEqual(detect_value_type(42.5), "number")

    def test_boolean_is_not_detected_as_integer(self) -> None:
        from field_matcher import detect_value_type

        self.assertEqual(detect_value_type(True), "boolean")

    def test_detects_email_format(self) -> None:
        from field_matcher import detect_value_format

        self.assertEqual(
            detect_value_format("qa_user@example.com"),
            "email",
        )

    def test_detects_uuid_format(self) -> None:
        from field_matcher import detect_value_format

        self.assertEqual(
            detect_value_format(
                "123e4567-e89b-12d3-a456-426614174000"
            ),
            "uuid",
        )

    def test_detects_date_time_format(self) -> None:
        from field_matcher import detect_value_format

        self.assertEqual(
            detect_value_format("2026-07-10T16:20:00Z"),
            "date-time",
        )

    def test_detects_phone_format(self) -> None:
        from field_matcher import detect_value_format

        self.assertEqual(
            detect_value_format("+90 555 123 45 67"),
            "phone",
        )

    def test_plain_string_has_no_known_format(self) -> None:
        from field_matcher import detect_value_format

        self.assertIsNone(
            detect_value_format("Test User")
        )


class OpenApiCompatibilityTests(unittest.TestCase):
    def test_email_value_matches_email_schema(self) -> None:
        from field_matcher import analyze_openapi_compatibility

        result = analyze_openapi_compatibility(
            "qa_user@example.com",
            {
                "type": "string",
                "format": "email",
            },
        )

        self.assertTrue(result.type_compatible)
        self.assertTrue(result.format_compatible)
        self.assertFalse(result.has_conflict)

    def test_plain_name_is_rejected_for_email_schema(self) -> None:
        from field_matcher import analyze_openapi_compatibility

        result = analyze_openapi_compatibility(
            "Test User",
            {
                "type": "string",
                "format": "email",
            },
        )

        self.assertTrue(result.type_compatible)
        self.assertFalse(result.format_compatible)
        self.assertTrue(result.has_conflict)

    def test_integer_matches_number_schema(self) -> None:
        from field_matcher import analyze_openapi_compatibility

        result = analyze_openapi_compatibility(
            42,
            {
                "type": "number",
            },
        )

        self.assertTrue(result.type_compatible)
        self.assertIsNone(result.format_compatible)
        self.assertFalse(result.has_conflict)

    def test_string_is_rejected_for_integer_schema(self) -> None:
        from field_matcher import analyze_openapi_compatibility

        result = analyze_openapi_compatibility(
            "42",
            {
                "type": "integer",
            },
        )

        self.assertFalse(result.type_compatible)
        self.assertTrue(result.has_conflict)

    def test_missing_schema_metadata_is_unknown_not_conflict(self) -> None:
        from field_matcher import analyze_openapi_compatibility

        result = analyze_openapi_compatibility(
            "some value",
            {},
        )

        self.assertIsNone(result.type_compatible)
        self.assertIsNone(result.format_compatible)
        self.assertFalse(result.has_conflict)
