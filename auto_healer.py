import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

from field_matcher import evaluate_field_match


PROJECT_ROOT = Path(__file__).resolve().parent
TEST_RUNNER_FILE = PROJECT_ROOT / "test_runner.py"

TEST_CASE_FILE = "api_test_case.yaml"
HEALED_TEST_FILE = "api_test_case.healed.yaml"
OPENAPI_FILE = "openapi.yaml"
HEAL_REPORT_FILE = "heal_report.md"

CREATE_PR = os.getenv("CREATE_PR", "false").lower() == "true"


def extract_status_codes(output):
    """
    Extract expected and actual status codes from test_runner.py output.

    Expected examples:
    [FAIL] Expected 201, got 400
    [PASS] Expected 201, got 201
    """
    match = re.search(r"Expected\s+(\d+),\s+got\s+(\d+)", output)
    if not match:
        return None, None

    expected_status = int(match.group(1))
    actual_status = int(match.group(2))
    return expected_status, actual_status


def run_test_case(file_path):
    """Run test_runner.py and return a structured result."""
    if not TEST_RUNNER_FILE.exists():
        message = f"test_runner.py was not found at: {TEST_RUNNER_FILE}"
        print(f"[ERROR] {message}")
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": message,
            "expected_status": None,
            "actual_status": None,
        }

    result = subprocess.run(
        [
            sys.executable,
            str(TEST_RUNNER_FILE),
            str(file_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    stdout = result.stdout.strip() if result.stdout else ""
    stderr = result.stderr.strip() if result.stderr else ""

    if stdout:
        print(stdout)

    if stderr:
        print(stderr)

    expected_status, actual_status = extract_status_codes(stdout)

    return {
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "expected_status": expected_status,
        "actual_status": actual_status,
    }


def run_command(command, error_message):
    """Run a command and return True only when it succeeds."""
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.stdout:
        print(result.stdout.strip())

    if result.returncode != 0:
        print(f"\n[ERROR] {error_message}")
        if result.stderr:
            print(result.stderr.strip())
        return False

    return True


def is_working_tree_clean():
    """
    Check whether tracked files are clean before creating a PR.

    Untracked and ignored generated files are intentionally ignored.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    return result.returncode == 0 and result.stdout.strip() == ""


def has_staged_changes():
    """Return True when staged changes are ready to commit."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
    )

    return result.returncode == 1


def get_current_git_branch():
    """Return the current Git branch, or None when it cannot be resolved."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.returncode != 0:
        return None

    branch_name = result.stdout.strip()
    return branch_name or None


def deterministic_heal(
    test_case_file=None,
    openapi_file=None,
    healed_test_file=None,
    dry_run=False,
):
    test_case_file = test_case_file or TEST_CASE_FILE
    openapi_file = openapi_file or OPENAPI_FILE
    healed_test_file = healed_test_file or HEALED_TEST_FILE

    print(
        f"\n[*] Healer: Starting drift analysis on "
        f"'{test_case_file}'..."
    )

    with open(test_case_file, "r", encoding="utf-8") as file:
        test_data = yaml.safe_load(file)

    with open(openapi_file, "r", encoding="utf-8") as file:
        openapi_data = yaml.safe_load(file)

    schema = (
        openapi_data["paths"]["/users"]["post"]
        ["requestBody"]["content"]["application/json"]["schema"]
    )

    required_fields = schema.get("required", [])
    properties = schema.get("properties", {})
    valid_properties = list(properties.keys())

    request_body = test_data.get("body", {})
    current_keys = list(request_body.keys())

    missing_required_fields = [
        field
        for field in required_fields
        if field not in current_keys
    ]

    invalid_existing_fields = [
        key
        for key in current_keys
        if key not in valid_properties
    ]

    if not missing_required_fields:
        print(
            "[-] No missing required fields. "
            "Contract drift not found."
        )
        return None

    if (
        len(missing_required_fields) == 1
        and len(invalid_existing_fields) == 1
    ):
        old_field = invalid_existing_fields[0]
        new_field = missing_required_fields[0]

        match_decision = evaluate_field_match(
            source_field=old_field,
            target_field=new_field,
            source_value=request_body[old_field],
            target_schema=properties.get(new_field, {}),
        )

        print(
            f"[*] Evaluating candidate match: "
            f"'{old_field}' -> '{new_field}'"
        )

        if not match_decision.safe_to_patch:
            print(
                f"[!] Unsafe field match rejected: "
                f"'{old_field}' -> '{new_field}'"
            )
            print(
                f"    Score: {match_decision.score:.3f} | "
                f"Threshold: {match_decision.threshold:.3f} | "
                f"Confidence: {match_decision.confidence}"
            )

            for reason in match_decision.reasons:
                print(f"    - {reason}")

            return None

        print(
            f"[+] Safe Drift Match Detected: "
            f"'{old_field}' -> '{new_field}'"
        )
        print(
            f"    Score: {match_decision.score:.3f} | "
            f"Confidence: {match_decision.confidence}"
        )

        heal_result = {
            "test_name": test_data.get("name", "Unknown Test"),
            "old_field": old_field,
            "new_field": new_field,
            "missing_required_fields": missing_required_fields,
            "invalid_existing_fields": invalid_existing_fields,
            "confidence": match_decision.confidence,
            "confidence_reason": (
                "The candidate field rename passed semantic, "
                "type, and format checks with a score of "
                f"{match_decision.score:.3f}, above the "
                f"{match_decision.threshold:.3f} safety threshold."
            ),
            "match_score": match_decision.score,
            "match_threshold": match_decision.threshold,
            "match_reasons": list(match_decision.reasons),
        }

        if dry_run:
            print(
                "[DRY RUN] Safe patch candidate accepted. "
                "No files were changed."
            )
            return heal_result

        request_body[new_field] = request_body.pop(old_field)
        test_data["body"] = request_body

        with open(healed_test_file, "w", encoding="utf-8") as file:
            yaml.dump(
                test_data,
                file,
                allow_unicode=True,
                sort_keys=False,
            )

        print(
            f"[+] Healed test file generated: "
            f"{healed_test_file}"
        )

        return heal_result

    print(
        "[!] Complex or multiple drift situation. "
        "Bypassing automatic intervention."
    )
    print(
        f"    Missing required fields: "
        f"{missing_required_fields}"
    )
    print(
        f"    Invalid existing fields: "
        f"{invalid_existing_fields}"
    )

    return None


def build_heal_report(report_data):
    generated_at = report_data["generated_at"]
    matching_evidence = "\n".join(
        f"- {reason}"
        for reason in report_data["match_reasons"]
        if not reason.startswith("Decision:")
    )

    return f"""# API Drift Healer Report

## Summary
API Drift Healer detected a contract drift, generated a safe patch, validated the healed test locally, and prepared a human-reviewable report for the fix.

## Test
`{report_data["test_name"]}`

## Root Cause
OpenAPI requires `{report_data["new_field"]}`, but the test case was sending `{report_data["old_field"]}`.

## Applied Fix
`{report_data["old_field"]}` -> `{report_data["new_field"]}`

## Validation
- Original test: Failed with `{report_data["original_actual_status"]}`
- Expected status: `{report_data["original_expected_status"]}`
- Healed test: Passed with `{report_data["healed_actual_status"]}`

## Confidence
`{report_data["confidence"]}`

## Confidence Reason
{report_data["confidence_reason"]}

## Smart Match Decision

- Match score: `{report_data["match_score"]:.3f}`
- Safety threshold: `{report_data["match_threshold"]:.3f}`
- Confidence: `{report_data["confidence"]}`
- Decision: `SAFE PATCH`

## Matching Evidence

{matching_evidence}

## Files
- Original test file: `{report_data["original_file"]}`
- Healed test file: `{report_data["healed_file"]}`
- OpenAPI contract: `{report_data["openapi_file"]}`

## Safety
This report was generated only after the healed test passed locally.

No PASS, No Apply.
No PASS, No PR.

## Generated At
`{generated_at}`
"""


def generate_heal_report(report_data, report_file=None):
    report_file = report_file or HEAL_REPORT_FILE
    report = build_heal_report(report_data)

    with open(report_file, "w", encoding="utf-8") as file:
        file.write(report)

    print(f"[+] Heal report generated: {report_file}")
    return report


def apply_validated_patch(healed_test_file, test_case_file):
    """Atomically replace the original test with the validated healed file."""
    healed_path = Path(healed_test_file)
    target_path = Path(test_case_file)
    temp_path = target_path.with_name(
        f".{target_path.name}.api-drift-healer.tmp"
    )

    try:
        shutil.copyfile(healed_path, temp_path)
        shutil.copymode(target_path, temp_path)
        os.replace(temp_path, target_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def create_secure_pr(
    old_field,
    new_field,
    pr_body,
    test_case_file=None,
    healed_test_file=None,
):
    """Create a reviewable PR after validation and return a success boolean."""
    test_case_file = test_case_file or TEST_CASE_FILE
    healed_test_file = healed_test_file or HEALED_TEST_FILE

    print(
        "\n[*] SECURITY LOCK RELEASED: "
        "PASS received. Initiating GitHub PR flow..."
    )

    if not is_working_tree_clean():
        print(
            "\n[ERROR] Working tree is not clean. "
            "Commit or stash tracked changes before creating a PR."
        )
        print("[INFO] PR flow stopped before creating a new branch.")
        return False

    original_branch = get_current_git_branch()
    if not original_branch:
        print("\n[ERROR] Could not determine the current Git branch.")
        return False

    safe_old = old_field.replace("_", "-").lower()
    safe_new = new_field.replace("_", "-").lower()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    branch_name = f"auto-heal/{safe_old}-to-{safe_new}-{timestamp}"
    branch_created = False

    try:
        if not run_command(
            ["git", "checkout", "-b", branch_name],
            "Failed to create a new Git branch.",
        ):
            return False

        branch_created = True
        apply_validated_patch(
            healed_test_file=healed_test_file,
            test_case_file=test_case_file,
        )

        print(
            f"[*] Committing and pushing changes to branch "
            f"'{branch_name}'..."
        )

        if not run_command(
            ["git", "add", str(test_case_file)],
            "Failed to stage the patched test file.",
        ):
            return False

        if not has_staged_changes():
            print(
                "\n[ERROR] No staged patch was detected after "
                "applying the healed test file."
            )
            print(
                "[INFO] PR flow stopped because there is "
                "nothing to commit."
            )
            return False

        if not run_command(
            ["git", "commit", "-m", "Auto-heal API test field drift"],
            "Failed to commit the patched test file.",
        ):
            return False

        if not run_command(
            ["git", "push", "-u", "origin", branch_name],
            "Failed to push the auto-heal branch.",
        ):
            return False

        pr_title = f"Auto-heal API test drift: {old_field} -> {new_field}"
        print("[*] Opening Pull Request via GitHub CLI (gh)...")

        pr_result = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                pr_title,
                "--body",
                pr_body,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        if pr_result.returncode != 0:
            print("\n[ERROR] Failed to open PR.")
            if pr_result.stderr:
                print(pr_result.stderr.strip())
            return False

        print("\n==================================================")
        print("[SUCCESS] HUMAN-REVIEWABLE AUTOMATION COMPLETED!")
        print(f"PR Link: {pr_result.stdout.strip()}")
        print("==================================================")
        return True

    finally:
        if branch_created:
            checkout_result = subprocess.run(
                ["git", "checkout", original_branch],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if checkout_result.returncode != 0:
                print(
                    f"[WARNING] Could not return to the original "
                    f"branch '{original_branch}'."
                )
                if checkout_result.stderr:
                    print(checkout_result.stderr.strip())


def run_healer(
    test_case_file=TEST_CASE_FILE,
    openapi_file=OPENAPI_FILE,
    healed_test_file=HEALED_TEST_FILE,
    report_file=HEAL_REPORT_FILE,
    create_pr=False,
    dry_run=False,
    apply_patch=False,
):
    """
    Run the complete API drift healing flow.

    Return codes:
        0: Original test already passes, dry-run succeeds, or healing succeeds.
        1: Healing, validation, apply, or PR creation fails.
        2: Invalid arguments, paths, or missing input files.
    """
    if dry_run and (apply_patch or create_pr):
        print(
            "[ERROR] Dry-run cannot be combined with "
            "apply or create-pr."
        )
        return 2

    if create_pr and not apply_patch:
        print("[ERROR] Create PR requires apply mode.")
        return 2

    test_path = Path(test_case_file).expanduser().resolve()
    openapi_path = Path(openapi_file).expanduser().resolve()
    healed_path = Path(healed_test_file).expanduser().resolve()
    report_path = Path(report_file).expanduser().resolve()

    if not test_path.is_file():
        print(f"[ERROR] Test file does not exist: {test_path}")
        return 2

    if not openapi_path.is_file():
        print(f"[ERROR] OpenAPI file does not exist: {openapi_path}")
        return 2

    if healed_path in {test_path, openapi_path}:
        print(
            "[ERROR] Healed output must be different from "
            "the test and OpenAPI files."
        )
        return 2

    if report_path in {test_path, openapi_path, healed_path}:
        print(
            "[ERROR] Report path must be different from the test, "
            "OpenAPI, and healed output files."
        )
        return 2

    if not dry_run:
        healed_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)

    test_case_file = str(test_path)
    openapi_file = str(openapi_path)
    healed_test_file = str(healed_path)
    report_file = str(report_path)

    print(
        "=== API DRIFT HEALER V0.6 "
        "(CLI HEALING FLOW) ==="
    )

    if not dry_run:
        if healed_path.exists():
            healed_path.unlink()

        if report_path.exists():
            report_path.unlink()

    print("\n[1] Running the original test case...")
    first_run = run_test_case(test_case_file)

    if first_run["returncode"] == 0:
        print(
            "\n[+] Test is already passing. "
            "No drift detected, skipping healer, apply, and PR."
        )
        return 0

    print("\n[!] Test FAILED! Triggering Healer...")

    heal_result = deterministic_heal(
        test_case_file=test_case_file,
        openapi_file=openapi_file,
        healed_test_file=healed_test_file,
        dry_run=dry_run,
    )

    if not heal_result:
        print(
            "\n[ERROR] Auto-healing failed or was flagged "
            "as risky. No apply or PR operation will run."
        )
        return 1

    old_field = heal_result["old_field"]
    new_field = heal_result["new_field"]

    if dry_run:
        print("\n[DRY RUN] Analysis completed successfully.")
        print(
            f"[DRY RUN] Candidate: "
            f"'{old_field}' -> '{new_field}'"
        )
        print(
            f"[DRY RUN] Score: "
            f"{heal_result['match_score']:.3f}"
        )
        print(
            f"[DRY RUN] Threshold: "
            f"{heal_result['match_threshold']:.3f}"
        )
        print("[DRY RUN] Decision: SAFE PATCH")
        print(
            "[DRY RUN] No healed test, report, apply, "
            "or PR operation was performed."
        )
        return 0

    print("\n[3] Automatically validating the healed test case...")
    healed_run = run_test_case(healed_test_file)

    if healed_run["returncode"] != 0:
        print(
            "\n[ERROR] Test file was patched, but the server "
            "still rejected it."
        )
        print("[ERROR] No apply or PR operation will be performed.")
        return 1

    print(
        "\n[PASS] Healed test validated successfully. "
        "Golden Rules satisfied."
    )

    print("\n[4] Generating explainability report...")

    report_data = {
        "test_name": heal_result["test_name"],
        "old_field": old_field,
        "new_field": new_field,
        "original_file": test_case_file,
        "healed_file": healed_test_file,
        "openapi_file": openapi_file,
        "original_expected_status": first_run["expected_status"],
        "original_actual_status": first_run["actual_status"],
        "healed_expected_status": healed_run["expected_status"],
        "healed_actual_status": healed_run["actual_status"],
        "confidence": heal_result["confidence"],
        "confidence_reason": heal_result["confidence_reason"],
        "match_score": heal_result["match_score"],
        "match_threshold": heal_result["match_threshold"],
        "match_reasons": heal_result["match_reasons"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    pr_body = generate_heal_report(
        report_data=report_data,
        report_file=report_file,
    )

    if create_pr:
        print("\n[5] Creating a human-reviewable Pull Request...")
        pr_created = create_secure_pr(
            old_field=old_field,
            new_field=new_field,
            pr_body=pr_body,
            test_case_file=test_case_file,
            healed_test_file=healed_test_file,
        )

        if not pr_created:
            return 1

    elif apply_patch:
        print(
            "\n[5] Applying validated patch "
            "to the original test file..."
        )

        try:
            apply_validated_patch(
                healed_test_file=healed_test_file,
                test_case_file=test_case_file,
            )
        except OSError as error:
            print(f"[ERROR] Failed to apply validated patch: {error}")
            return 1

        print(
            f"[APPLIED] Validated patch applied to: "
            f"{test_case_file}"
        )
        print("[APPLIED] Golden Rule satisfied: No PASS, no apply.")

    else:
        print(
            "\n[5] Apply and PR creation skipped. "
            "Healed output and report are available for review."
        )

    return 0


def main():
    exit_code = run_healer(
        test_case_file=TEST_CASE_FILE,
        openapi_file=OPENAPI_FILE,
        healed_test_file=HEALED_TEST_FILE,
        report_file=HEAL_REPORT_FILE,
        create_pr=CREATE_PR,
        dry_run=False,
        apply_patch=CREATE_PR,
    )

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()