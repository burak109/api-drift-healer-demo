import unittest

from api_drift_healer.adapters.http_file import (
    HttpFilePatchError,
    parse_http_request,
    patch_http_request_body,
)


class HttpFilePatcherTests(unittest.TestCase):
    def test_renames_only_top_level_json_key(self) -> None:
        source = (
            "### Create User\n"
            "POST http://localhost:3000/users\n"
            "Content-Type: application/json\n"
            "X-Test: keep-me\n"
            "\n"
            "{\n"
            '  "name": "Test User",\n'
            '  "userEmail": "qa_user@example.com",\n'
            '  "note": "userEmail should stay",\n'
            '  "nested": {\n'
            '    "userEmail": "nested should stay"\n'
            "  }\n"
            "}\n"
        )

        parsed = parse_http_request(
            source,
            name="create-user",
        )

        patched = patch_http_request_body(
            parsed,
            old_field="userEmail",
            new_field="email_address",
        )

        self.assertIn(
            '"email_address": "qa_user@example.com"',
            patched,
        )
        self.assertIn(
            '"userEmail": "nested should stay"',
            patched,
        )
        self.assertIn(
            '"note": "userEmail should stay"',
            patched,
        )
        self.assertIn(
            "X-Test: keep-me",
            patched,
        )

        restored = patched.replace(
            '"email_address"',
            '"userEmail"',
            1,
        )

        self.assertEqual(restored, source)

    def test_patches_compact_json_body(self) -> None:
        source = (
            "POST /users\n"
            "Content-Type: application/json\n"
            "\n"
            '{"userEmail":"qa_user@example.com"}'
        )

        parsed = parse_http_request(source)

        patched = patch_http_request_body(
            parsed,
            "userEmail",
            "email_address",
        )

        self.assertIn(
            '{"email_address":"qa_user@example.com"}',
            patched,
        )

    def test_rejects_missing_top_level_field(self) -> None:
        source = (
            "POST /users\n"
            "\n"
            '{"name": "Test User"}'
        )

        parsed = parse_http_request(source)

        with self.assertRaisesRegex(
            HttpFilePatchError,
            "was not found",
        ):
            patch_http_request_body(
                parsed,
                "userEmail",
                "email_address",
            )

    def test_rejects_existing_new_field(self) -> None:
        source = (
            "POST /users\n"
            "\n"
            "{\n"
            '  "userEmail": "old@example.com",\n'
            '  "email_address": "new@example.com"\n'
            "}"
        )

        parsed = parse_http_request(source)

        with self.assertRaisesRegex(
            HttpFilePatchError,
            "already exists",
        ):
            patch_http_request_body(
                parsed,
                "userEmail",
                "email_address",
            )


if __name__ == "__main__":
    unittest.main()