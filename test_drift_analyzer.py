import unittest

from api_drift_healer.drift_analyzer import (
    DriftAnalyzerError,
    analyze_request_drift,
)
from api_drift_healer.models import (
    NormalizedRequest,
    ResolvedRequestSchema,
)


def make_schema(
    *,
    path: str = "/users",
    method: str = "POST",
    required_fields: tuple[str, ...] = ("email_address",),
    properties: dict | None = None,
) -> ResolvedRequestSchema:
    if properties is None:
        properties = {
            "name": {
                "type": "string",
            },
            "email_address": {
                "type": "string",
                "format": "email",
            },
        }

    return ResolvedRequestSchema(
        path=path,
        method=method,
        required_fields=required_fields,
        properties=properties,
    )


class DriftAnalyzerTests(unittest.TestCase):
    def test_safe_email_rename_is_accepted(self) -> None:
        request = NormalizedRequest(
            name="Create User",
            method="POST",
            path="/users",
            body={
                "name": "Test User",
                "userEmail": "qa_user@example.com",
            },
        )

        result = analyze_request_drift(
            request=request,
            schema=make_schema(),
        )

        self.assertEqual(result.decision, "SAFE_PATCH")
        self.assertTrue(result.safe_to_patch)
        self.assertEqual(result.old_field, "userEmail")
        self.assertEqual(result.new_field, "email_address")
        self.assertGreaterEqual(
            result.score,
            result.threshold,
        )

    def test_unsafe_name_to_email_is_rejected(self) -> None:
        request = NormalizedRequest(
            name="Create User",
            method="POST",
            path="/users",
            body={
                "name": "Test User",
                "displayName": "Test User",
            },
        )

        result = analyze_request_drift(
            request=request,
            schema=make_schema(),
        )

        self.assertEqual(result.decision, "REJECTED")
        self.assertFalse(result.safe_to_patch)
        self.assertEqual(result.old_field, "displayName")
        self.assertEqual(result.new_field, "email_address")
        self.assertLess(
            result.score,
            result.threshold,
        )

    def test_returns_no_drift_when_required_fields_exist(self) -> None:
        request = NormalizedRequest(
            name="Create User",
            method="POST",
            path="/users",
            body={
                "name": "Test User",
                "email_address": "qa_user@example.com",
            },
        )

        result = analyze_request_drift(
            request=request,
            schema=make_schema(),
        )

        self.assertEqual(result.decision, "NO_DRIFT")
        self.assertFalse(result.safe_to_patch)
        self.assertEqual(result.missing_required_fields, ())

    def test_returns_complex_drift_for_multiple_candidates(self) -> None:
        request = NormalizedRequest(
            name="Create User",
            method="POST",
            path="/users",
            body={
                "name": "Test User",
                "userEmail": "qa_user@example.com",
                "phoneNumber": "+905551112233",
            },
        )

        schema = make_schema(
            required_fields=(
                "email_address",
                "phone_number",
            ),
            properties={
                "name": {
                    "type": "string",
                },
                "email_address": {
                    "type": "string",
                    "format": "email",
                },
                "phone_number": {
                    "type": "string",
                },
            },
        )

        result = analyze_request_drift(
            request=request,
            schema=schema,
        )

        self.assertEqual(
            result.decision,
            "COMPLEX_DRIFT",
        )
        self.assertEqual(
            result.missing_required_fields,
            (
                "email_address",
                "phone_number",
            ),
        )
        self.assertEqual(
            result.invalid_existing_fields,
            (
                "userEmail",
                "phoneNumber",
            ),
        )

    def test_rejects_method_mismatch(self) -> None:
        request = NormalizedRequest(
            name="Create User",
            method="POST",
            path="/users",
            body={},
        )

        schema = make_schema(method="PUT")

        with self.assertRaisesRegex(
            DriftAnalyzerError,
            "method",
        ):
            analyze_request_drift(
                request=request,
                schema=schema,
            )

    def test_rejects_path_mismatch(self) -> None:
        request = NormalizedRequest(
            name="Create User",
            method="POST",
            path="/users",
            body={},
        )

        schema = make_schema(path="/customers")

        with self.assertRaisesRegex(
            DriftAnalyzerError,
            "path",
        ):
            analyze_request_drift(
                request=request,
                schema=schema,
            )

    def test_does_not_mutate_request_body(self) -> None:
        request = NormalizedRequest(
            name="Create User",
            method="POST",
            path="/users",
            body={
                "name": "Test User",
                "userEmail": "qa_user@example.com",
            },
        )

        analyze_request_drift(
            request=request,
            schema=make_schema(),
        )

        self.assertEqual(
            request.body,
            {
                "name": "Test User",
                "userEmail": "qa_user@example.com",
            },
        )


if __name__ == "__main__":
    unittest.main()
