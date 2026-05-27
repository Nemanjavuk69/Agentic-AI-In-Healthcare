import json
import os
import signal
import socket
import subprocess
import sys
import time
from typing import Dict, Any, List, Optional

import requests

BOOKING_API_SCRIPT = "booking_api.py"
BOOKING_API_URL = os.environ.get("BOOKING_API_URL", "http://localhost:8000/book")
BOOKING_API_KEY = os.environ.get("BOOKING_API_KEY", "demo-secret")
TIMEOUT = 5

TEST_PATIENT_ID = "P-TEST01"
TEST_HOSPITAL = "Aalborg University Hospital"


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def wait_for_server(url: str, timeout: float = 5.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            requests.post(url.replace("/book", "/invalid"), timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def start_api_server() -> subprocess.Popen:
    if is_port_open("localhost", 8000):
        raise RuntimeError(
            "Port 8000 is already in use. Stop any existing booking_api.py process before running this test."
        )

    env = os.environ.copy()
    env["BOOKING_API_KEY"] = BOOKING_API_KEY

    process = subprocess.Popen(
        [sys.executable, BOOKING_API_SCRIPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )

    if not wait_for_server(BOOKING_API_URL, timeout=5):
        stdout, stderr = process.communicate(timeout=2)
        raise RuntimeError(
            f"booking_api.py did not start correctly.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    return process


def stop_api_server(process: Optional[subprocess.Popen]) -> None:
    if not process:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()


def make_headers(token: Optional[str] = None, content_type: str = "application/json") -> Dict[str, str]:
    headers = {"Content-Type": content_type}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def valid_payload() -> Dict[str, Any]:
    return {
        "hospital": TEST_HOSPITAL,
        "specialty": "cardiology",
        "time": "2025-06-10 09:30",
        "patient_id": TEST_PATIENT_ID
    }


def safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


def evaluate_success_schema(data: Dict[str, Any]) -> bool:
    required = {"status", "booking_ref", "hospital", "specialty", "time"}
    return required.issubset(data.keys())


def run_case(
    name: str,
    method: str = "POST",
    url: str = BOOKING_API_URL,
    token: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    raw_body: Optional[str] = None,
    expected_status: Optional[int] = None,
) -> Dict[str, Any]:
    headers = make_headers(token=token)

    try:
        if raw_body is not None:
            response = requests.request(
                method,
                url,
                data=raw_body,
                headers=headers,
                timeout=TIMEOUT
            )
        else:
            response = requests.request(
                method,
                url,
                json=payload,
                headers=headers,
                timeout=TIMEOUT
            )

        body = safe_json(response)

        passed = response.status_code == expected_status if expected_status is not None else True

        return {
            "test": name,
            "passed": passed,
            "status_code": response.status_code,
            "headers_sent": headers,
            "response_body": body
        }

    except Exception as e:
        return {
            "test": name,
            "passed": False,
            "status_code": None,
            "headers_sent": headers,
            "response_body": str(e)
        }


def run_tests() -> List[Dict[str, Any]]:
    results = []

    # 1. Valid token + valid payload
    case = run_case(
        name="valid_token_valid_payload",
        token=BOOKING_API_KEY,
        payload=valid_payload(),
        expected_status=200
    )
    if case["passed"] and isinstance(case["response_body"], dict):
        body = case["response_body"]
        case["passed"] = (
            evaluate_success_schema(body)
            and body["hospital"] == TEST_HOSPITAL
            and body["specialty"] == "cardiology"
        )
    results.append(case)

    # 2. Missing token
    results.append(run_case(
        name="missing_token",
        token=None,
        payload=valid_payload(),
        expected_status=401
    ))

    # 3. Wrong token
    results.append(run_case(
        name="wrong_token",
        token="wrong-secret",
        payload=valid_payload(),
        expected_status=401
    ))

    # 4. Missing required field
    bad_payload = valid_payload()
    bad_payload.pop("patient_id")
    results.append(run_case(
        name="missing_required_field",
        token=BOOKING_API_KEY,
        payload=bad_payload,
        expected_status=400
    ))

    # 5. Malformed JSON
    results.append(run_case(
        name="malformed_json",
        token=BOOKING_API_KEY,
        raw_body='{"hospital": "Aalborg", "specialty": "cardiology", bad_json}',
        expected_status=400
    ))

    # 6. Wrong path
    results.append(run_case(
        name="wrong_path",
        url="http://localhost:8000/invalid",
        token=BOOKING_API_KEY,
        payload=valid_payload(),
        expected_status=404
    ))

    return results


def print_results(results: List[Dict[str, Any]]) -> None:
    print("=" * 110)
    print("AGENT 3 TOOLCHAIN MITIGATION TEST")
    print("=" * 110)

    passed_count = 0
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        if result["passed"]:
            passed_count += 1

        print(f"{status:<6} | {result['test']:<26} | HTTP {str(result['status_code']):<4} | headers={result['headers_sent']}")
        print(f"       response={result['response_body']}")

    print("-" * 110)
    print(f"Passed {passed_count}/{len(results)} tests.")

    print("\nInterpretation:")
    print("- A PASS on valid_token_valid_payload means the protected booking path still works.")
    print("- PASSES on missing_token and wrong_token mean authentication is actually enforced.")
    print("- PASSES on malformed_json and missing_required_field mean request validation is active.")
    print("- A PASS on wrong_path means the API surface is limited to the intended endpoint.")


def print_auth_diagnosis(results: List[Dict[str, Any]]) -> None:
    failed_auth_tests = [r for r in results if r["test"] in ("missing_token", "wrong_token") and not r["passed"]]

    if not failed_auth_tests:
        print("\nAuth diagnosis: bearer-token enforcement appears to be working correctly.")
        return

    print("\nAuth diagnosis:")
    print("- Authentication is NOT being enforced by the running API instance.")
    print("- Most likely causes:")
    print("  1. booking_api.py started with BOOKING_API_KEY unset or empty.")
    print("  2. Another old server process is already listening on port 8000.")
    print("  3. The wrong booking_api.py file is being executed.")
    print("  4. The test is targeting a different endpoint than expected.")
    print(f"- Expected BOOKING_API_KEY for this test run: {BOOKING_API_KEY!r}")


def main():
    process = None
    try:
        print(f"Starting booking API with BOOKING_API_KEY={BOOKING_API_KEY!r}")
        process = start_api_server()
        results = run_tests()
        print_results(results)
        print_auth_diagnosis(results)
    finally:
        stop_api_server(process)


if __name__ == "__main__":
    main()