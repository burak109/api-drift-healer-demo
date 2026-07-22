import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_drift_healer.adapters.postman import (
    load_postman_collection,
    normalize_postman_request,
    write_postman_collection,
)
from api_drift_healer.newman_runner import NewmanRunResult
from api_drift_healer.postman_validator import (
    PostmanValidationError,
    validate_postman_heal,
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
    """Create a Postman collection with a custom request body."""

    collection = load_postman_collection(
        EXAMPLE_COLLECTION
    )

    request_body = (
        collection["item"][0]["item"][0]["request"]["body"]
    )

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


def make_newman_result(
    collection_path: str | Path,
    return_code: int,
    environment_path: str | Path | None = None,
) -> NewmanRunResult:
    """Create one fake Newman result."""

    resolved_collection = (
        Path(collection_path).expanduser().resolve()
    )

    resolved_environment = (
        Path(environment_path).expanduser().resolve()
        if environment_path is not None
        else None
    )

    return NewmanRunResult(
        collection_path=resolved_collection,
        environment_path=resolved_environment,
        command=(
            "newman",
            "run",
            str(resolved_collection),
        ),
        return_code=return_code,
        stdout=(
            "Newman run passed."
            if return_code == 0
            else "Newman run failed."
        ),
        stderr="",
    )


def newman_result_sequence(
    *return_codes: int,
):
    """Build a mock Newman runner with sequential results."""

    remaining_codes = list(return_codes)

    def fake_run(
        collection_path: str | Path,
        environment_path: str | Path | None = None,
        **kwargs,
    ) -> NewmanRunResult:
        del kwargs

        if not remaining_codes:
            raise AssertionError(
                "Newman runner was called more times than expected."
            )

        return make_newman_result(
            collection_path=collection_path,
            environment_path=environment_path,
            return_code=remaining_codes.pop(0),
        )

    return fake_run


class PostmanValidatorTests(unittest.TestCase):
    def test_not_patchable_collection_skips_newman(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_path = Path(directory)

            collection_path = create_collection_variant(
                directory=temp_path,
                body={
                    "name": "Test User",
                    "email_address": "qa_user@example.com",
                },
            )

            output_path = (
                temp_path
                / "should-not-exist.json"
            )

            with patch(
                "api_drift_healer.postman_validator."
                "run_newman_collection"
            ) as run_mock:
                result = validate_postman_heal(
                    collection_path=collection_path,
                    openapi_path=EXAMPLE_OPENAPI,
                    request_name="Create User",
                    output_path=output_path,
                )

            self.assertEqual(
                result.decision,
                "NOT_PATCHABLE",
            )

            self.assertFalse(result.validated)
            self.assertFalse(result.written)
            self.assertFalse(output_path.exists())

            run_mock.assert_not_called()

    def test_original_pass_prevents_validated_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "healed.postman_collection.json"
            )

            with patch(
                "api_drift_healer.postman_validator."
                "run_newman_collection",
                side_effect=newman_result_sequence(0),
            ) as run_mock:
                result = validate_postman_heal(
                    collection_path=EXAMPLE_COLLECTION,
                    openapi_path=EXAMPLE_OPENAPI,
                    request_name="Create User",
                    output_path=output_path,
                )

            self.assertEqual(
                result.decision,
                "ORIGINAL_PASSED",
            )

            self.assertIsNotNone(result.original_run)
            self.assertIsNone(result.healed_run)
            self.assertFalse(result.validated)
            self.assertFalse(output_path.exists())

            self.assertEqual(
                run_mock.call_count,
                1,
            )

    def test_healed_failure_prevents_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "healed.postman_collection.json"
            )

            with patch(
                "api_drift_healer.postman_validator."
                "run_newman_collection",
                side_effect=newman_result_sequence(
                    1,
                    1,
                ),
            ) as run_mock:
                result = validate_postman_heal(
                    collection_path=EXAMPLE_COLLECTION,
                    openapi_path=EXAMPLE_OPENAPI,
                    request_name="Create User",
                    output_path=output_path,
                )

            self.assertEqual(
                result.decision,
                "HEALED_FAILED",
            )

            self.assertIsNotNone(result.original_run)
            self.assertIsNotNone(result.healed_run)
            self.assertFalse(result.validated)
            self.assertFalse(result.written)
            self.assertFalse(output_path.exists())

            self.assertEqual(
                run_mock.call_count,
                2,
            )

    def test_original_fail_and_healed_pass_writes_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "healed.postman_collection.json"
            )

            with patch(
                "api_drift_healer.postman_validator."
                "run_newman_collection",
                side_effect=newman_result_sequence(
                    1,
                    0,
                ),
            ):
                result = validate_postman_heal(
                    collection_path=EXAMPLE_COLLECTION,
                    openapi_path=EXAMPLE_OPENAPI,
                    request_name="Create User",
                    output_path=output_path,
                )

            self.assertEqual(
                result.decision,
                "VALIDATED",
            )

            self.assertTrue(result.validated)
            self.assertTrue(result.written)
            self.assertEqual(
                result.output_path,
                output_path.resolve(),
            )

            healed_collection = load_postman_collection(
                output_path
            )

            healed_request = normalize_postman_request(
                collection=healed_collection,
                request_name="Create User",
            )

            self.assertIn(
                "email_address",
                healed_request.body,
            )

            self.assertNotIn(
                "userEmail",
                healed_request.body,
            )

    def test_environment_is_forwarded_to_both_runs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_path = Path(directory)

            environment_path = (
                temp_path
                / "demo.postman_environment.json"
            )

            environment_path.write_text(
                "{}",
                encoding="utf-8",
            )

            output_path = (
                temp_path
                / "healed.postman_collection.json"
            )

            with patch(
                "api_drift_healer.postman_validator."
                "run_newman_collection",
                side_effect=newman_result_sequence(
                    1,
                    0,
                ),
            ) as run_mock:
                result = validate_postman_heal(
                    collection_path=EXAMPLE_COLLECTION,
                    openapi_path=EXAMPLE_OPENAPI,
                    request_name="Create User",
                    environment_path=environment_path,
                    output_path=output_path,
                )

            self.assertTrue(result.validated)
            self.assertEqual(
                run_mock.call_count,
                2,
            )

            for run_call in run_mock.call_args_list:
                self.assertEqual(
                    Path(
                        run_call.kwargs[
                            "environment_path"
                        ]
                    ).resolve(),
                    environment_path.resolve(),
                )

    def test_original_pass_guard_can_be_disabled(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "healed.postman_collection.json"
            )

            with patch(
                "api_drift_healer.postman_validator."
                "run_newman_collection",
                side_effect=newman_result_sequence(
                    0,
                    0,
                ),
            ):
                result = validate_postman_heal(
                    collection_path=EXAMPLE_COLLECTION,
                    openapi_path=EXAMPLE_OPENAPI,
                    request_name="Create User",
                    output_path=output_path,
                    require_original_failure=False,
                )

            self.assertEqual(
                result.decision,
                "VALIDATED",
            )

            self.assertTrue(result.validated)
            self.assertTrue(output_path.exists())

    def test_source_collection_cannot_be_overwritten(
        self,
    ) -> None:
        with (
            patch(
                "api_drift_healer.postman_validator."
                "run_newman_collection"
            ) as run_mock,
            self.assertRaisesRegex(
                PostmanValidationError,
                "different from",
            ),
        ):
            validate_postman_heal(
                collection_path=EXAMPLE_COLLECTION,
                openapi_path=EXAMPLE_OPENAPI,
                request_name="Create User",
                output_path=EXAMPLE_COLLECTION,
                overwrite=True,
            )

        run_mock.assert_not_called()

    def test_existing_output_requires_overwrite(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "existing.postman_collection.json"
            )

            output_path.write_text(
                "{}",
                encoding="utf-8",
            )

            with (
                patch(
                    "api_drift_healer.postman_validator."
                    "run_newman_collection"
                ) as run_mock,
                self.assertRaisesRegex(
                    PostmanValidationError,
                    "already exists",
                ),
            ):
                validate_postman_heal(
                    collection_path=EXAMPLE_COLLECTION,
                    openapi_path=EXAMPLE_OPENAPI,
                    request_name="Create User",
                    output_path=output_path,
                )

            run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()