"""
Test suite for call_llm() mitigations:
  - Test 1: API key is injected into Authorization header
  - Test 2: call_llm() works without a token (backward compatibility)
  - Test 3: LLM output containing PII is sanitized before returning
  - Test 4: No sanitization when analyzer/anonymizer are not passed
"""

import json
import os
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

# ── Point to your actual utils.py ───────────────────────────────────────────
from utils import call_llm, setup_analyzer_and_anonymizer, sanitize_text


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_mock_response(content: str):
    """Simulates the HTTP response object returned by urllib.request.urlopen."""
    body = json.dumps({
        "message": {"content": content}
    }).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCallLLMMitigations(unittest.TestCase):

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 1
    # Verifies that when OLLAMA_API_KEY is set, the Authorization header
    # is present in the request sent to the Ollama endpoint.
    # ─────────────────────────────────────────────────────────────────────────
    def test_bearer_token_is_sent_when_env_var_set(self):
        os.environ["OLLAMA_API_KEY"] = "test-secret-token"

        # Reload the module-level OLLAMA_TOKEN after env var change
        import utils
        utils.OLLAMA_TOKEN = os.environ.get("OLLAMA_API_KEY", "")

        captured_request = {}

        def mock_urlopen(req):
            # Capture the request headers so we can inspect them
            captured_request["headers"] = dict(req.headers)
            return make_mock_response("some LLM reply")

        with patch("utils.urllib.request.urlopen", side_effect=mock_urlopen):
            result = call_llm("You are a doctor.", "Patient has fever.")

        auth_header = captured_request["headers"].get("Authorization", "")
        self.assertEqual(
            auth_header,
            "Bearer test-secret-token",
            "Authorization header was not set correctly."
        )
        print("✅ TEST 1 PASSED — Bearer token present in request headers")

        # Cleanup
        del os.environ["OLLAMA_API_KEY"]
        utils.OLLAMA_TOKEN = ""

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 2
    # Verifies backward compatibility: when no token is configured,
    # no Authorization header is sent and the call still succeeds.
    # ─────────────────────────────────────────────────────────────────────────
    def test_no_auth_header_when_token_not_set(self):
        import utils
        utils.OLLAMA_TOKEN = ""   # explicitly clear

        captured_request = {}

        def mock_urlopen(req):
            captured_request["headers"] = dict(req.headers)
            return make_mock_response("some LLM reply")

        with patch("utils.urllib.request.urlopen", side_effect=mock_urlopen):
            result = call_llm("You are a doctor.", "Patient has fever.")

        self.assertNotIn(
            "Authorization",
            captured_request["headers"],
            "Authorization header should NOT be present when no token is set."
        )
        self.assertEqual(result, "some LLM reply")
        print("✅ TEST 2 PASSED — No Authorization header when token is empty")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 3
    # Verifies that when the LLM echoes back PII (e.g. a medication name
    # attached to a person's name), the output is sanitized before returning.
    # ─────────────────────────────────────────────────────────────────────────
    def test_output_pii_is_sanitized(self):
        analyzer, anonymizer = setup_analyzer_and_anonymizer()

        # Simulate LLM echoing back a name from the prompt context
        pii_response = (
            "Patient John Smith should take lisinopril 10mg daily. "
            "Contact him at john.smith@email.com if symptoms worsen."
        )

        with patch("utils.urllib.request.urlopen",
                   return_value=make_mock_response(pii_response)):
            result = call_llm(
                "You are a medical assistant.",
                "Provide advice.",
                analyzer=analyzer,
                anonymizer=anonymizer
            )

        # After sanitization, the name and email must be replaced
        self.assertNotIn("John Smith", result,
                         "Person name was not redacted from LLM output.")
        self.assertNotIn("john.smith@email.com", result,
                         "Email address was not redacted from LLM output.")
        print(f"✅ TEST 3 PASSED — PII sanitized from LLM output")
        print(f"   Raw    : {pii_response}")
        print(f"   Cleaned: {result}")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 4
    # Verifies that when no analyzer/anonymizer are passed, the raw LLM
    # output is returned unchanged (existing call sites are unaffected).
    # ─────────────────────────────────────────────────────────────────────────
    def test_no_sanitization_when_engines_not_passed(self):
        raw_response = "Patient John Smith should rest at home."

        with patch("utils.urllib.request.urlopen",
                   return_value=make_mock_response(raw_response)):
            result = call_llm(
                "You are a medical assistant.",
                "Provide advice."
                # No analyzer/anonymizer passed — backward compatible
            )

        self.assertEqual(result, raw_response,
                         "Output should be unchanged when no sanitizer is passed.")
        print("✅ TEST 4 PASSED — Raw output returned when no sanitizer passed")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  call_llm() Mitigation Tests")
    print("=" * 60 + "\n")
    unittest.main(verbosity=0)