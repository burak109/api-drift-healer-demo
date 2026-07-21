import unittest

from api_drift_healer.models import NormalizedRequest


class NormalizedRequestTests(unittest.TestCase):
    def test_normalizes_method_and_path(self) -> None:
        request = NormalizedRequest(
            name="Create User",
            method="post",
            path="users",
            body={"name": "Test User"},
        )

        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/users")

    def test_trims_request_name(self) -> None:
        request = NormalizedRequest(
            name="  Create User  ",
            method="POST",
            path="/users",
            body={},
        )

        self.assertEqual(request.name, "Create User")

    def test_keeps_already_normalized_path(self) -> None:
        request = NormalizedRequest(
            name="Get User",
            method="GET",
            path="/users",
            body={},
        )

        self.assertEqual(request.path, "/users")

    def test_copies_body_dictionary(self) -> None:
        original_body = {"userEmail": "qa_user@example.com"}

        request = NormalizedRequest(
            name="Create User",
            method="POST",
            path="/users",
            body=original_body,
        )

        original_body["name"] = "Changed Later"

        self.assertNotIn("name", request.body)

    def test_rejects_empty_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "name"):
            NormalizedRequest(
                name=" ",
                method="POST",
                path="/users",
                body={},
            )

    def test_rejects_empty_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            NormalizedRequest(
                name="Create User",
                method=" ",
                path="/users",
                body={},
            )

    def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "path"):
            NormalizedRequest(
                name="Create User",
                method="POST",
                path=" ",
                body={},
            )

    def test_rejects_non_dictionary_body(self) -> None:
        with self.assertRaisesRegex(TypeError, "dictionary"):
            NormalizedRequest(
                name="Create User",
                method="POST",
                path="/users",
                body=[],  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
