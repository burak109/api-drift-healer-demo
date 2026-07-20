import yaml
import os
import subprocess
import sys
import shutil
import re
from datetime import datetime
from field_matcher import evaluate_field_match

TEST_CASE_FILE = "api_test_case.yaml"
HEALED_TEST_FILE = "api_test_case.healed.yaml"
OPENAPI_FILE = "openapi.yaml"
HEAL_REPORT_FILE = "heal_report.md"

CREATE_PR = os.getenv("CREATE_PR", "false").lower() == "true"



def extract_status_codes(output):
    """
    Extracts expected and actual status codes from test_runner.py output.
    Expected output example:
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
    """
    Runs test_runner.py as a subprocess and returns a structured result.
    """
    result = subprocess.run(
        [sys.executable, "test_runner.py", file_path],
        capture_output=True,
        text=True,
        encoding="utf-8"
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
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8"
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
    Checks whether tracked files are clean before creating a PR.
    Ignored/generated files are not a problem.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    return result.stdout.strip() == ""


def has_staged_changes():
    """
    Returns True if there are staged changes ready to commit.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True
    )

    return result.returncode == 1


def deterministic_heal(
    test_case_file=None,
    openapi_file=None,
    healed_test_file=None,
):
    test_case_file = test_case_file or TEST_CASE_FILE
    openapi_file = openapi_file or OPENAPI_FILE
    healed_test_file = healed_test_file or HEALED_TEST_FILE

    print(
        f"\n[*] Healer: Starting drift analysis on "
        f"'{test_case_file}'..."
    )

    with open(test_case_file, "r", encoding="utf-8") as f:
        test_data = yaml.safe_load(f)

    with open(openapi_file, "r", encoding="utf-8") as f:
        openapi_data = yaml.safe_load(f)

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

        request_body[new_field] = request_body.pop(old_field)
        test_data["body"] = request_body

        with open(
            healed_test_file,
            "w",
            encoding="utf-8",
        ) as f:
            yaml.dump(
                test_data,
                f,
                allow_unicode=True,
                sort_keys=False,
            )

        print(
            f"[+] Healed test file generated for demo: "
            f"{healed_test_file}"
        )

        return {
            "test_name": test_data.get(
                "name",
                "Unknown Test",
            ),
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

No PASS, No PR.

## Generated At
`{generated_at}`
"""


def generate_heal_report(
    report_data,
    report_file=None,
):
    report_file = report_file or HEAL_REPORT_FILE

    report = build_heal_report(report_data)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[+] Heal report generated: {report_file}")

    return report


def create_secure_pr(
    old_field,
    new_field,
    pr_body,
    test_case_file=None,
    healed_test_file=None,
):
    test_case_file = test_case_file or TEST_CASE_FILE
    healed_test_file = healed_test_file or HEALED_TEST_FILE

    print(
        "\n[*] SECURITY LOCK RELEASED: "
        "PASS received. Initiating GitHub PR flow..."
    )

    if not is_working_tree_clean():
        print("\n[ERROR] Working tree is not clean. Commit or stash your changes before creating a PR.")
        print("[INFO] PR flow stopped before creating a new branch.")
        return

    safe_old = old_field.replace("_", "-").lower()
    safe_new = new_field.replace("_", "-").lower()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    branch_name = f"auto-heal/{safe_old}-to-{safe_new}-{timestamp}"

    if not run_command(
        ["git", "checkout", "-b", branch_name],
        "Failed to create a new git branch."
    ):
        return

    shutil.copyfile(
    healed_test_file,
    test_case_file,
)

    print(f"[*] Committing and pushing changes to branch '{branch_name}'...")

    if not run_command(
        ["git", "add", str(test_case_file)],
        "Failed to stage the patched test file."
    ):
        return
    if not has_staged_changes():
        print("\n[ERROR] No staged patch was detected after applying the healed test file.")
        print("[INFO] PR flow stopped because there is nothing to commit.")
        subprocess.run(["git", "checkout", "main"], capture_output=True)
        return

    if not run_command(
        ["git", "commit", "-m", "Auto-heal API test field drift"],
        "Failed to commit the patched test file."
    ):
        return

    if not run_command(
        ["git", "push", "-u", "origin", branch_name],
        "Failed to push the auto-heal branch."
    ):
        return

    pr_title = f"Auto-heal API test drift: {old_field} -> {new_field}"

    print("[*] Opening Pull Request via GitHub CLI (gh)...")

    pr_res = subprocess.run(
        [
            "gh", "pr", "create",
            "--title", pr_title,
            "--body", pr_body
        ],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    if pr_res.returncode == 0:
        print("\n==================================================")
        print("[SUCCESS] HUMAN-REVIEWED AUTOMATION COMPLETED!")
        print(f"PR Link: {pr_res.stdout.strip()}")
        print("==================================================")
    else:
        print("\n[ERROR] Failed to open PR.")
        if pr_res.stderr:
            print(pr_res.stderr.strip())

    subprocess.run(["git", "checkout", "main"], capture_output=True)


def main():
    print("=== API DRIFT HEALER V0.4 (SAFE SMART FIELD MATCHING) ===")

    if os.path.exists(HEALED_TEST_FILE):
        os.remove(HEALED_TEST_FILE)

    if os.path.exists(HEAL_REPORT_FILE):
        os.remove(HEAL_REPORT_FILE)

    print("\n[1] Running the original test case...")
    first_run = run_test_case(TEST_CASE_FILE)

    if first_run["returncode"] == 0:
        print("\n[+] Test is already passing. No drift detected, skipping healer and PR.")
        sys.exit(0)

    print("\n[!] Test FAILED! Triggering Healer...")

    heal_result = deterministic_heal()

    if not heal_result:
        print("\n[ERROR] Auto-healing failed or flagged as risky. No PR will be opened.")
        sys.exit(1)

    old_field = heal_result["old_field"]
    new_field = heal_result["new_field"]

    print("\n[3] Automatically validating the healed test case...")
    healed_run = run_test_case(HEALED_TEST_FILE)

    if healed_run["returncode"] != 0:
        print("\n[ERROR] Test file patched but server still rejected it (FAIL). NO PR WILL BE OPENED!")
        sys.exit(1)

    print("\n[PASS] Healed test validated successfully. Golden Rule (No PASS, No PR) satisfied!")

    print("\n[4] Generating explainability report...")

    report_data = {
        "test_name": heal_result["test_name"],
        "old_field": old_field,
        "new_field": new_field,
        "original_file": TEST_CASE_FILE,
        "healed_file": HEALED_TEST_FILE,
        "openapi_file": OPENAPI_FILE,
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

    pr_body = generate_heal_report(report_data)

    if CREATE_PR:
        print("\n[5] Creating a human-reviewable Pull Request...")
        create_secure_pr(old_field, new_field, pr_body)
    else:
        print("\n[5] PR creation skipped. Local V0.4 report mode is active.")


if __name__ == "__main__":
    main()