import json
import tempfile
import unittest
from pathlib import Path

from api_drift_healer.adapters.postman import (
    load_postman_collection,
    normalize_postman_request,
    write_postman_collection,
)
from api_drift_healer.postman_healer import (
    PostmanHealError,
    heal_postman_collection,
)


PROJECT_ROOT = Path(__file__).resolve().parent
EXAMPLE_COLLECTION = (
    PROJECT_ROOT
    / "examples"
    / "postman"
    / "create-user.postman_collection.json"
)
EXAMPLE_OPENAPI = (
    PROJECT_ROOT
    / "examples"
    / "postman"
    / "openapi.yaml"
)


def create_collection_variant(
    directory: Path,
    body: dict,
) -> Path:
    collection = load_postman_collection(
        EXAMPLE_COLLECTION
    )

    request_body = collection[
        "item"
    ][0][
        "item"
    ][0][
        "request"
    ][
        "body"
    ]

    request_body["raw"] = json.dumps(
        body,
        indent=2,
    )

    collection_path = (
        directory
        / "variant.postman_collection.json"
    )

    write_postman_collection(
        collection=collection,
        output_path=collection_path,
    )

    return collection_path


class PostmanHealerTests(unittest.TestCase):
    def test_safe_flow_writes_healed_collection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "healed.postman_collection.json"
            )

            result = heal_postman_collection(
                collection_path=EXAMPLE_COLLECTION,
                openapi_path=EXAMPLE_OPENAPI,
                request_name="Create User",
                output_path=output_path,
            )

            healed_collection = load_postman_collection(
                output_path
            )

            healed_request = normalize_postman_request(
                collection=healed_collection,
                request_name="Create User",
            )

            self.assertTrue(result.written)
            self.assertEqual(
                result.output_path,
                output_path.resolve(),
            )
            self.assertIn(
                "email_address",
                healed_request.body,
            )
            self.assertNotIn(
                "userEmail",
                healed_request.body,
            )

    def test_safe_flow_generates_body_diff(self) -> None:
        result = heal_postman_collection(
            collection_path=EXAMPLE_COLLECTION,
            openapi_path=EXAMPLE_OPENAPI,
            request_name="Create User",
            dry_run=True,
        )

        self.assertEqual(
            result.analysis.decision,
            "SAFE_PATCH",
        )
        self.assertIn(
            '-  "userEmail": "qa_user@example.com"',
            result.diff,
        )
        self.assertIn(
            '+  "email_address": "qa_user@example.com"',
            result.diff,
        )

    def test_dry_run_does_not_write_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "should-not-exist.json"
            )

            result = heal_postman_collection(
                collection_path=EXAMPLE_COLLECTION,
                openapi_path=EXAMPLE_OPENAPI,
                request_name="Create User",
                output_path=output_path,
                dry_run=True,
            )

            self.assertFalse(result.written)
            self.assertFalse(output_path.exists())
            self.assertIn(
                "email_address",
                result.after_body,
            )

    def test_rejected_candidate_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_path = Path(directory)

            source_path = create_collection_variant(
                directory=temp_path,
                body={
                    "name": "Test User",
                    "displayName": "Test User",
                },
            )

            output_path = temp_path / "rejected.json"

            result = heal_postman_collection(
                collection_path=source_path,
                openapi_path=EXAMPLE_OPENAPI,
                request_name="Create User",
                output_path=output_path,
            )

            self.assertEqual(
                result.analysis.decision,
                "REJECTED",
            )
            self.assertFalse(result.written)
            self.assertFalse(output_path.exists())
            self.assertEqual(result.diff, "")

    def test_no_drift_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_path = Path(directory)

            source_path = create_collection_variant(
                directory=temp_path,
                body={
                    "name": "Test User",
                    "email_address": "qa_user@example.com",
                },
            )

            output_path = temp_path / "no-drift.json"

            result = heal_postman_collection(
                collection_path=source_path,
                openapi_path=EXAMPLE_OPENAPI,
                request_name="Create User",
                output_path=output_path,
            )

            self.assertEqual(
                result.analysis.decision,
                "NO_DRIFT",
            )
            self.assertFalse(result.written)
            self.assertFalse(output_path.exists())

    def test_refuses_to_overwrite_source_collection(self) -> None:
        with self.assertRaisesRegex(
            PostmanHealError,
            "different from",
        ):
            heal_postman_collection(
                collection_path=EXAMPLE_COLLECTION,
                openapi_path=EXAMPLE_OPENAPI,
                request_name="Create User",
                output_path=EXAMPLE_COLLECTION,
                overwrite=True,
            )


if __name__ == "__main__":
    unittest.main()
