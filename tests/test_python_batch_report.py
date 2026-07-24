import unittest
from types import SimpleNamespace

from api_drift_healer.models import DriftAnalysisResult
from api_drift_healer.python_batch_report import (
    build_python_batch_report,
    format_python_batch_report,
)


class PythonBatchReportTests(unittest.TestCase):
    def _analysis_result(
        self,
        decision: str,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            analysis=DriftAnalysisResult(
                decision=decision,
                request_name=f"request-{decision}",
                missing_required_fields=(),
                invalid_existing_fields=(),
            )
        )

    def _validation_result(self) -> SimpleNamespace:
        analysis = SimpleNamespace(
            files_scanned=3,
            requests_discovered=4,
            requests_analyzed=4,
            results=(
                self._analysis_result("NO_DRIFT"),
                self._analysis_result("SAFE_PATCH"),
                self._analysis_result("REJECTED"),
                self._analysis_result("COMPLEX_DRIFT"),
            ),
            scan_errors=("scan error",),
            analysis_errors=("analysis error",),
        )

        plan = SimpleNamespace(
            analysis=analysis,
            patches=("patch",),
            patch_errors=("patch error",),
        )

        return SimpleNamespace(
            plan=plan,
            validations=(
                SimpleNamespace(validated=True),
            ),
            validation_errors=("validation error",),
        )

    def test_builds_aggregate_batch_report(self) -> None:
        validation_result = self._validation_result()

        report = build_python_batch_report(
            validation_result
        )

        self.assertEqual(report.files_scanned, 3)
        self.assertEqual(report.requests_discovered, 4)
        self.assertEqual(report.requests_analyzed, 4)

        self.assertEqual(report.no_drift, 1)
        self.assertEqual(report.drifts_detected, 3)
        self.assertEqual(report.safe_patch_decisions, 1)
        self.assertEqual(report.rejected_drifts, 1)
        self.assertEqual(report.complex_drifts, 1)

        self.assertEqual(report.patches_generated, 1)
        self.assertEqual(report.patches_validated, 1)
        self.assertEqual(report.validation_failures, 0)

        self.assertEqual(report.pipeline_errors, 4)

    def test_counts_failed_patch_validations(self) -> None:
        validation_result = self._validation_result()

        validation_result.validations = (
            SimpleNamespace(validated=True),
            SimpleNamespace(validated=False),
        )

        report = build_python_batch_report(
            validation_result
        )

        self.assertEqual(report.patches_validated, 1)
        self.assertEqual(report.validation_failures, 1)

    def test_formats_human_readable_report(self) -> None:
        report = build_python_batch_report(
            self._validation_result()
        )

        output = format_python_batch_report(report)

        expected_lines = (
            "Files scanned: 3",
            "Requests discovered: 4",
            "Requests analyzed: 4",
            "No drift: 1",
            "Drift detected: 3",
            "Safe patch decisions: 1",
            "Rejected drift: 1",
            "Complex drift: 1",
            "Patches generated: 1",
            "Patches validated: 1",
            "Validation failures: 0",
            "Pipeline errors: 4",
        )

        for expected_line in expected_lines:
            self.assertIn(expected_line, output)


if __name__ == "__main__":
    unittest.main()
