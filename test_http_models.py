import unittest

from api_drift_healer.models import (
    NormalizedRequest,
    ParsedHttpRequest,
)


def make_request() -> NormalizedRequest:
    return NormalizedRequest(
        name="create-user",
        method="POST",
        path="/users",
        body={
            "name": "Test User",
            "userEmail": "qa_user@example.com",
        },
    )


class ParsedHttpRequestTests(unittest.TestCase):
    def test_keeps_source_body_positions(self) -> None:
        source = (
            "POST http://localhost:3000/users\n"
            "Content-Type: application/json\n"
            "\n"
            "{\n"
            '  "name": "Test User",\n'
            '  "userEmail": "qa_user@example.com"\n'
            "}\n"
        )

        body_start = source.index("{")
        body_end = source.rindex("}") + 1

        parsed = ParsedHttpRequest(
            request=make_request(),
            source_text=source,
            body_start=body_start,
            body_end=body_end,
            newline="\n",
        )

        self.assertTrue(
            parsed.body_text.startswith("{")
        )
        self.assertTrue(
            parsed.body_text.endswith("}")
        )
        self.assertIn(
            '"userEmail"',
            parsed.body_text,
        )

    def test_supports_crlf_newlines(self) -> None:
        source = (
            "POST http://localhost:3000/users\r\n"
            "\r\n"
            "{}\r\n"
        )

        body_start = source.index("{")
        body_end = source.index("}") + 1

        parsed = ParsedHttpRequest(
            request=make_request(),
            source_text=source,
            body_start=body_start,
            body_end=body_end,
            newline="\r\n",
        )

        self.assertEqual(parsed.newline, "\r\n")
        self.assertEqual(parsed.body_text, "{}")

    def test_rejects_negative_body_start(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "cannot be negative",
        ):
            ParsedHttpRequest(
                request=make_request(),
                source_text="{}",
                body_start=-1,
                body_end=2,
                newline="\n",
            )

    def test_rejects_body_end_before_start(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "before body start",
        ):
            ParsedHttpRequest(
                request=make_request(),
                source_text="{}",
                body_start=2,
                body_end=1,
                newline="\n",
            )

    def test_rejects_body_end_after_source(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "exceed source length",
        ):
            ParsedHttpRequest(
                request=make_request(),
                source_text="{}",
                body_start=0,
                body_end=3,
                newline="\n",
            )

    def test_rejects_unsupported_newline(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "LF or CRLF",
        ):
            ParsedHttpRequest(
                request=make_request(),
                source_text="{}",
                body_start=0,
                body_end=2,
                newline="\r",
            )


if __name__ == "__main__":
    unittest.main()
