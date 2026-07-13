import unittest

from field_matcher import normalize_field_name, normalized_field_text


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


if __name__ == "__main__":
    unittest.main()
