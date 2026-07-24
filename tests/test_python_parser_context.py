import unittest

from api_drift_healer.python_parser import parse_python_source


class PythonRequestContextTests(unittest.TestCase):
    def test_associates_requests_with_test_functions(self) -> None:
        source = '''
import requests


def test_create_user():
    payload = {
        "userEmail": "create@example.com",
    }

    requests.post(
        "http://localhost:3000/users",
        json=payload,
    )


def test_update_user():
    requests.put(
        "http://localhost:3000/users/1",
        json={
            "userEmail": "update@example.com",
        },
    )
'''

        result = parse_python_source(source)

        self.assertEqual(len(result.requests), 2)

        create_request = result.requests[0]
        update_request = result.requests[1]

        self.assertEqual(
            create_request.test_name,
            "test_create_user",
        )
        self.assertEqual(
            update_request.test_name,
            "test_update_user",
        )

        self.assertEqual(
            create_request.line_number,
            10,
        )
        self.assertEqual(
            update_request.line_number,
            17,
        )

    def test_module_level_request_has_no_test_name(self) -> None:
        source = '''
import requests

requests.post(
    "http://localhost:3000/users",
    json={
        "userEmail": "module@example.com",
    },
)
'''

        result = parse_python_source(source)

        self.assertEqual(len(result.requests), 1)
        self.assertIsNone(
            result.requests[0].test_name,
        )

    def test_non_test_function_has_no_test_name(self) -> None:
        source = '''
import requests


def create_user_helper():
    requests.post(
        "http://localhost:3000/users",
        json={
            "userEmail": "helper@example.com",
        },
    )
'''

        result = parse_python_source(source)

        self.assertEqual(len(result.requests), 1)
        self.assertIsNone(
            result.requests[0].test_name,
        )


if __name__ == "__main__":
    unittest.main()
