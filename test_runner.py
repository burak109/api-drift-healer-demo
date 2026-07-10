import yaml
import requests
import sys


def run_test(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        test_case = yaml.safe_load(f)

    print(f"\n[*] Running test: {test_case['name']} ({file_path})")

    try:
        response = requests.request(
            method=test_case["method"],
            url=test_case["url"],
            json=test_case["body"],
            timeout=3
        )
    except Exception as e:
        print(f"[FAIL] Could not reach server: {e}")
        return 1

    if response.status_code == test_case["expected_status"]:
        print(f"[PASS] Expected {test_case['expected_status']}, got {response.status_code}")
        return 0
    else:
        print(f"[FAIL] Expected {test_case['expected_status']}, got {response.status_code}")

        try:
            print(f"       Error: {response.json().get('error')}")
        except Exception:
            print(f"       Response: {response.text}")

        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[!] Usage: python test_runner.py <test_file.yaml>")
        sys.exit(1)

    sys.exit(run_test(sys.argv[1]))