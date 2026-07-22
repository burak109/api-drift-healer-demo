import unittest

from api_drift_healer.adapters.http_file import (
    HttpFileParseError,
    parse_http_request,
)


class HttpFileAdapterTests(unittest.TestCase):
    def test_parses_single_http_request(self) -> None:
        source = (
            "POST http://localhost:3000/users\n"
            "Content-Type: application/json\n"
            "\n"
            "{\n"
            '  "name": "Test User",\n'
            '  "userEmail": "qa_user@example.com"\n'
            "}\n"
        )

        parsed = parse_http_request(
            source,
            name="create-user",
        )

        self.assertEqual(parsed.request.name, "create-user")
        self.assertEqual(parsed.request.method, "POST")
        self.assertEqual(parsed.request.path, "/users")
        self.assertEqual(
            parsed.request.body["userEmail"],
            "qa_user@example.com",
        )
        self.assertEqual(parsed.newline, "\n")

    def test_removes_query_string_from_path(self) -> None:
        source = (
            "PATCH /users/42?source=test\n"
            "Content-Type: application/json\n"
            "\n"
            '{"userEmail": "qa_user@example.com"}'
        )

        parsed = parse_http_request(source)

        self.assertEqual(parsed.request.path, "/users/42")
        self.assertEqual(parsed.request.method, "PATCH")

    def test_preserves_crlf_newline_type(self) -> None:
        source = (
            "POST http://localhost:3000/users\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            '{"userEmail": "qa_user@example.com"}\r\n'
        )

        parsed = parse_http_request(source)

        self.assertEqual(parsed.newline, "\r\n")
        self.assertIn('"userEmail"', parsed.body_text)

    def test_rejects_multiple_requests(self) -> None:
        source = (
            "### Create User\n"
            "POST http://localhost:3000/users\n"
            "\n"
            "{}\n"
            "\n"
            "### Get User\n"
            "GET http://localhost:3000/users/1\n"
            "\n"
        )

        with self.assertRaisesRegex(
            HttpFileParseError,
            "Multiple requests detected",
        ):
            parse_http_request(source)

    def test_rejects_invalid_json_body(self) -> None:
        source = (
            "POST http://localhost:3000/users\n"
            "Content-Type: application/json\n"
            "\n"
            '{"userEmail": }'
        )

        with self.assertRaisesRegex(
            HttpFileParseError,
            "not valid JSON",
        ):
            parse_http_request(source)


if __name__ == "__main__":
    unittest.main()