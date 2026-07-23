import unittest

from api_drift_healer.python_parser import (
    PythonParseError,
    parse_python_source,
)


class PythonRequestParserTests(unittest.TestCase):
    def test_detects_named_payload_for_requests_post(self) -> None:
        source = '''
import requests

payload = {
    "name": "Test User",
    "userEmail": "qa_user@example.com",
}

response = requests.post(
    "http://localhost:3000/users",
    json=payload,
)
'''

        result = parse_python_source(source)

        self.assertEqual(len(result.requests), 1)

        request = result.requests[0]

        self.assertEqual(request.method, "POST")
        self.assertEqual(
            request.url,
            "http://localhost:3000/users",
        )
        self.assertEqual(
            request.payload.variable_name,
            "payload",
        )
        self.assertEqual(
            request.payload.fields,
            ("name", "userEmail"),
        )
        self.assertEqual(
            request.payload.values,
            {
                "name": "Test User",
                "userEmail": "qa_user@example.com",
            },
        )
        self.assertEqual(result.skipped_reasons, ())

    def test_detects_inline_dictionary_payload(self) -> None:
        source = '''
import requests

requests.put(
    "http://localhost:3000/users/1",
    json={
        "name": "Updated User",
        "userEmail": "updated@example.com",
    },
)
'''

        result = parse_python_source(source)

        self.assertEqual(len(result.requests), 1)

        request = result.requests[0]

        self.assertEqual(request.method, "PUT")
        self.assertIsNone(request.payload.variable_name)
        self.assertEqual(
            request.payload.fields,
            ("name", "userEmail"),
        )
        self.assertEqual(
            request.payload.values,
            {
                "name": "Updated User",
                "userEmail": "updated@example.com",
            },
        )

    def test_detects_url_keyword_argument(self) -> None:
        source = '''
import requests

payload = {"userEmail": "qa_user@example.com"}

requests.patch(
    url="http://localhost:3000/users/1",
    json=payload,
)
'''

        result = parse_python_source(source)

        self.assertEqual(len(result.requests), 1)
        self.assertEqual(
            result.requests[0].method,
            "PATCH",
        )
        self.assertEqual(
            result.requests[0].url,
            "http://localhost:3000/users/1",
        )
        self.assertEqual(
            result.requests[0].payload.values,
            {
                "userEmail": "qa_user@example.com",
            },
        )

    def test_ignores_unsupported_get_request(self) -> None:
        source = '''
import requests

requests.get("http://localhost:3000/users")
'''

        result = parse_python_source(source)

        self.assertEqual(result.requests, ())
        self.assertEqual(result.skipped_reasons, ())

    def test_skips_dynamic_url(self) -> None:
        source = '''
import requests

base_url = "http://localhost:3000"
payload = {"userEmail": "qa_user@example.com"}

requests.post(
    f"{base_url}/users",
    json=payload,
)
'''

        result = parse_python_source(source)

        self.assertEqual(result.requests, ())
        self.assertEqual(
            result.skipped_reasons,
            ("Line 7: dynamic or missing request URL",),
        )

    def test_skips_payload_created_by_function(self) -> None:
        source = '''
import requests

payload = build_payload()

requests.post(
    "http://localhost:3000/users",
    json=payload,
)
'''

        result = parse_python_source(source)

        self.assertEqual(result.requests, ())
        self.assertEqual(
            result.skipped_reasons,
            (
                "Line 6: unsupported or missing json payload",
            ),
        )

    def test_skips_payload_with_dynamic_value(self) -> None:
        source = '''
import requests

email = get_test_email()

payload = {
    "name": "Test User",
    "userEmail": email,
}

requests.post(
    "http://localhost:3000/users",
    json=payload,
)
'''

        result = parse_python_source(source)

        self.assertEqual(result.requests, ())
        self.assertEqual(
            len(result.skipped_reasons),
            1,
        )
        self.assertIn(
            "unsupported or missing json payload",
            result.skipped_reasons[0],
        )

    def test_rejects_invalid_python_source(self) -> None:
        source = '''
payload = {
    "name": "Test User",
'''

        with self.assertRaises(PythonParseError):
            parse_python_source(source)


if __name__ == "__main__":
    unittest.main()