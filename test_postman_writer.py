import json
import tempfile
import unittest
from pathlib import Path

from api_drift_healer.adapters.postman import (
    PostmanAdapterError,
    default_healed_collection_path,
    load_postman_collection,
    normalize_postman_request,
    patch_postman_request_body,
    write_postman_collection,
)


EXAMPLE_COLLECTION = Path(
    "examples/postman/create-user.postman_collection.json"
)


class PostmanWriterTests(unittest.TestCase):
    def test_builds_default_healed_collection_path(self) -> None:
        result = default_healed_collection_path(
            EXAMPLE_COLLECTION
        )

        self.assertEqual(
            result.name,
            "create-user.healed.postman_collection.json",
        )

    def test_writes_healed_collection_file(self) -> None:
        collection = load_postman_collection(
            EXAMPLE_COLLECTION
        )

        patched = patch_postman_request_body(
            collection=collection,
            request_name="Create User",
            old_field="userEmail",
            new_field="email_address",
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "create-user.healed.postman_collection.json"
            )

            result = write_postman_collection(
                collection=patched,
                output_path=output_path,
            )

            written_collection = load_postman_collection(
                result
            )

            request = normalize_postman_request(
                collection=written_collection,
                request_name="Create User",
            )

        self.assertEqual(result, output_path)
        self.assertIn(
            "email_address",
            request.body,
        )
        self.assertNotIn(
            "userEmail",
            request.body,
        )

    def test_written_file_is_valid_pretty_json(self) -> None:
        collection = load_postman_collection(
            EXAMPLE_COLLECTION
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "output.json"

            write_postman_collection(
                collection=collection,
                output_path=output_path,
            )

            raw_text = output_path.read_text(
                encoding="utf-8"
            )

            parsed = json.loads(raw_text)

        self.assertTrue(raw_text.endswith("\n"))
        self.assertIn("\n  ", raw_text)
        self.assertIsInstance(parsed, dict)

    def test_refuses_to_overwrite_existing_file(self) -> None:
        collection = load_postman_collection(
            EXAMPLE_COLLECTION
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "output.json"

            output_path.write_text(
                "existing",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                PostmanAdapterError,
                "already exists",
            ):
                write_postman_collection(
                    collection=collection,
                    output_path=output_path,
                )

    def test_overwrites_when_explicitly_enabled(self) -> None:
        collection = load_postman_collection(
            EXAMPLE_COLLECTION
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "output.json"

            output_path.write_text(
                "existing",
                encoding="utf-8",
            )

            write_postman_collection(
                collection=collection,
                output_path=output_path,
                overwrite=True,
            )

            parsed = json.loads(
                output_path.read_text(encoding="utf-8")
            )

        self.assertEqual(
            parsed["info"]["name"],
            "API Drift Healer Postman Demo",
        )


if __name__ == "__main__":
    unittest.main()
