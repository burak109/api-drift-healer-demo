import json
import unittest

from api_drift_healer.github_pr_report import (
    COMMENT_MARKER,
    GitHubPullRequestReportError,
    build_github_pr_report,
    format_github_pr_report,
    format_github_pr_report_json,
    parse_github_pr_report_json,
)


class GitHubPullRequestReportTests(unittest.TestCase):
    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "files_scanned": 3,
            "requests_discovered": 3,
            "requests_analyzed": 3,
            "no_drift": 2,
            "drifts_detected": 1,
            "safe_patch_decisions": 1,
            "rejected_drifts": 0,
            "complex_drifts": 0,
            "patches_generated": 1,
            "patches_validated": 1,
            "validation_failures": 0,
            "pipeline_errors": 0,
            "source_files_changed": False,
        }

    def test_builds_validated_report(self) -> None:
        report = build_github_pr_report(
            self._payload()
        )

        self.assertEqual(report.schema_version, 1)
        self.assertEqual(report.files_scanned, 3)
        self.assertEqual(report.drifts_detected, 1)
        self.assertEqual(report.patches_validated, 1)
        self.assertFalse(report.source_files_changed)

    def test_parses_json_report(self) -> None:
        report = parse_github_pr_report_json(
            json.dumps(self._payload())
        )

        self.assertEqual(
            report.requests_analyzed,
            3,
        )

    def test_formats_drift_status(self) -> None:
        output = format_github_pr_report_json(
            json.dumps(self._payload())
        )

        self.assertIn(
            "**Status:** ⚠️ API drift detected",
            output,
        )
        self.assertIn(
            "| Drifts detected | 1 |",
            output,
        )
        self.assertIn(
            "Source files changed: **No**",
            output,
        )

    def test_formats_no_drift_status(self) -> None:
        payload = self._payload()
        payload["no_drift"] = 3
        payload["drifts_detected"] = 0
        payload["safe_patch_decisions"] = 0
        payload["patches_generated"] = 0
        payload["patches_validated"] = 0

        output = format_github_pr_report_json(
            json.dumps(payload)
        )

        self.assertIn(
            "**Status:** ✅ No API drift detected",
            output,
        )

    def test_formats_attention_required_status(self) -> None:
        payload = self._payload()
        payload["validation_failures"] = 1

        report = build_github_pr_report(
            payload
        )
        output = format_github_pr_report(
            report
        )

        self.assertIn(
            "**Status:** ❌ Attention required",
            output,
        )

    def test_reports_source_file_modification(self) -> None:
        payload = self._payload()
        payload["source_files_changed"] = True

        output = format_github_pr_report_json(
            json.dumps(payload)
        )

        self.assertIn(
            (
                "**Status:** "
                "❌ Source-file modification detected"
            ),
            output,
        )
        self.assertIn(
            "Source files changed: **Yes**",
            output,
        )

    def test_comment_marker_appears_once(self) -> None:
        output = format_github_pr_report_json(
            json.dumps(self._payload())
        )

        self.assertEqual(
            output.count(COMMENT_MARKER),
            1,
        )
        self.assertTrue(
            output.startswith(COMMENT_MARKER)
        )

    def test_rejects_invalid_json(self) -> None:
        with self.assertRaisesRegex(
            GitHubPullRequestReportError,
            "not valid JSON",
        ):
            parse_github_pr_report_json(
                "{invalid-json"
            )

    def test_rejects_non_object_json(self) -> None:
        with self.assertRaisesRegex(
            GitHubPullRequestReportError,
            "must contain an object",
        ):
            parse_github_pr_report_json(
                "[]"
            )

    def test_rejects_missing_required_field(self) -> None:
        payload = self._payload()
        del payload["pipeline_errors"]

        with self.assertRaisesRegex(
            GitHubPullRequestReportError,
            "pipeline_errors",
        ):
            build_github_pr_report(
                payload
            )

    def test_rejects_unsupported_schema(self) -> None:
        payload = self._payload()
        payload["schema_version"] = 2

        with self.assertRaisesRegex(
            GitHubPullRequestReportError,
            "Unsupported report schema version",
        ):
            build_github_pr_report(
                payload
            )

    def test_rejects_boolean_metric(self) -> None:
        payload = self._payload()
        payload["files_scanned"] = True

        with self.assertRaisesRegex(
            GitHubPullRequestReportError,
            "files_scanned",
        ):
            build_github_pr_report(
                payload
            )

    def test_rejects_negative_metric(self) -> None:
        payload = self._payload()
        payload["pipeline_errors"] = -1

        with self.assertRaisesRegex(
            GitHubPullRequestReportError,
            "cannot be negative",
        ):
            build_github_pr_report(
                payload
            )

    def test_rejects_non_boolean_source_flag(self) -> None:
        payload = self._payload()
        payload["source_files_changed"] = "false"

        with self.assertRaisesRegex(
            GitHubPullRequestReportError,
            "must be a boolean",
        ):
            build_github_pr_report(
                payload
            )


if __name__ == "__main__":
    unittest.main()
