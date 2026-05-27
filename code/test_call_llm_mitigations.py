"""
Advanced mitigation test suite for call_llm().

Focus: LLM as a Tool subsection
- Transport/configuration controls
- Request payload integrity
- Output sanitization of echoed PII
- Clinical-context preservation
- Failure behavior visibility

"""

import json
import inspect
import re
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from utils import call_llm, setup_analyzer_and_anonymizer


def make_mock_response(content: str):
    body = json.dumps({"message": {"content": content}}).encode("utf-8")
    mock = MagicMock()
    mock.read.return_value = body
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def make_custom_json_response(payload_dict: dict):
    body = json.dumps(payload_dict).encode("utf-8")
    mock = MagicMock()
    mock.read.return_value = body
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


class TestLLMTransportMitigations(unittest.TestCase):
    """Transport, configuration, and request-construction tests."""

    def test_auth_1_bearer_token_sent_when_configured(self):
        import utils
        original_token = utils.OLLAMA_TOKEN
        utils.OLLAMA_TOKEN = "semester-project-token"
        captured = {}

        def mock_urlopen(req):
            captured["headers"] = dict(req.headers)
            return make_mock_response("ok")

        with patch("utils.urllib.request.urlopen", side_effect=mock_urlopen):
            result = call_llm("system prompt", "user prompt")

        self.assertEqual(result, "ok")
        self.assertEqual(
            captured["headers"].get("Authorization"),
            "Bearer semester-project-token",
            "Bearer token was not included in request headers."
        )
        utils.OLLAMA_TOKEN = original_token
        print("✅ AUTH-1 PASSED — Bearer token included when configured")

    def test_auth_2_no_auth_header_when_token_absent(self):
        import utils
        original_token = utils.OLLAMA_TOKEN
        utils.OLLAMA_TOKEN = ""
        captured = {}

        def mock_urlopen(req):
            captured["headers"] = dict(req.headers)
            return make_mock_response("ok")

        with patch("utils.urllib.request.urlopen", side_effect=mock_urlopen):
            result = call_llm("system prompt", "user prompt")

        self.assertEqual(result, "ok")
        self.assertNotIn(
            "Authorization",
            captured["headers"],
            "Authorization header should not be present when token is empty."
        )
        utils.OLLAMA_TOKEN = original_token
        print("✅ AUTH-2 PASSED — No Authorization header when token absent")

    def test_auth_3_custom_ollama_url_is_used(self):
        import utils
        original_url = utils.OLLAMA_URL
        utils.OLLAMA_URL = "http://secure-proxy.hospital.local:9000/api/chat"
        captured = {}

        def mock_urlopen(req):
            captured["url"] = req.full_url
            return make_mock_response("ok")

        with patch("utils.urllib.request.urlopen", side_effect=mock_urlopen):
            call_llm("system prompt", "user prompt")

        self.assertEqual(
            captured["url"],
            "http://secure-proxy.hospital.local:9000/api/chat",
            "Overridden OLLAMA_URL was not used."
        )
        utils.OLLAMA_URL = original_url
        print("✅ AUTH-3 PASSED — Custom OLLAMA_URL honoured")

    def test_auth_4_request_payload_structure_is_correct(self):
        captured = {}

        def mock_urlopen(req):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return make_mock_response("ok")

        with patch("utils.urllib.request.urlopen", side_effect=mock_urlopen):
            call_llm("You are a triage assistant.", "Patient has chest pain.")

        payload = captured["payload"]

        self.assertEqual(payload["model"], "qwen2.5:3b")
        self.assertEqual(payload["stream"], False)
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][0]["content"], "You are a triage assistant.")
        self.assertEqual(payload["messages"][1]["role"], "user")
        self.assertEqual(payload["messages"][1]["content"], "Patient has chest pain.")
        print("✅ AUTH-4 PASSED — JSON payload structure is correct")

    def test_auth_5_token_is_sourced_from_environment_not_hardcoded(self):
        import utils
        source = inspect.getsource(utils)

        self.assertIn(
            'os.environ.get("OLLAMA_API_KEY", "")',
            source,
            "OLLAMA_API_KEY environment lookup missing from utils.py."
        )

        hardcoded_pattern = re.compile(r'OLLAMA_TOKEN\s*=\s*["\'](?!["\'])[^"\']+["\']')
        match = hardcoded_pattern.search(source)
        self.assertIsNone(
            match,
            "OLLAMA_TOKEN appears to be hardcoded in source."
        )
        print("✅ AUTH-5 PASSED — Token sourced from environment, not hardcoded")


class TestLLMOutputSanitization(unittest.TestCase):
    """Output sanitization and privacy-preserving behavior."""

    @classmethod
    def setUpClass(cls):
        cls.analyzer, cls.anonymizer = setup_analyzer_and_anonymizer()

    def test_sanit_1_name_and_email_redacted(self):
        raw = "Patient John Smith should rest. Contact john.smith@hospital.dk."
        with patch("utils.urllib.request.urlopen", return_value=make_mock_response(raw)):
            result = call_llm(
                "sys",
                "user",
                analyzer=self.analyzer,
                anonymizer=self.anonymizer
            )

        self.assertNotIn("John Smith", result)
        self.assertNotIn("john.smith@hospital.dk", result)
        self.assertIn("<PERSON>", result)
        self.assertIn("<EMAIL_ADDRESS>", result)
        print("✅ SANIT-1 PASSED — Name and email redacted")
        print("   Raw    :", raw)
        print("   Cleaned:", result)

    def test_sanit_2_danish_cpr_redacted(self):
        raw = "Patient CPR is 010190-1234 and should stay home."
        with patch("utils.urllib.request.urlopen", return_value=make_mock_response(raw)):
            result = call_llm(
                "sys",
                "user",
                analyzer=self.analyzer,
                anonymizer=self.anonymizer
            )

        self.assertNotIn("010190-1234", result)
        self.assertIn("<DANISH_CPR>", result)
        print("✅ SANIT-2 PASSED — Danish CPR redacted")
        print("   Raw    :", raw)
        print("   Cleaned:", result)

    def test_sanit_3_phone_number_redacted(self):
        raw = "Call the patient at +45 20 30 40 50 if no improvement."
        with patch("utils.urllib.request.urlopen", return_value=make_mock_response(raw)):
            result = call_llm(
                "sys",
                "user",
                analyzer=self.analyzer,
                anonymizer=self.anonymizer
            )

        self.assertNotIn("+45 20 30 40 50", result)
        self.assertIn("<PHONE_NUMBER>", result)
        print("✅ SANIT-3 PASSED — Phone number redacted")
        print("   Raw    :", raw)
        print("   Cleaned:", result)

    def test_sanit_4_multiple_entities_redacted_together(self):
        raw = (
            "Patient Anna Larsen (CPR 150875-2345) can be reached at "
            "anna.larsen@clinic.dk or +45 31 22 44 66. She should rest."
        )
        with patch("utils.urllib.request.urlopen", return_value=make_mock_response(raw)):
            result = call_llm(
                "sys",
                "user",
                analyzer=self.analyzer,
                anonymizer=self.anonymizer
            )

        self.assertNotIn("Anna Larsen", result)
        self.assertNotIn("150875-2345", result)
        self.assertNotIn("anna.larsen@clinic.dk", result)
        self.assertNotIn("+45 31 22 44 66", result)
        self.assertIn("<PERSON>", result)
        self.assertIn("<DANISH_CPR>", result)
        self.assertIn("<EMAIL_ADDRESS>", result)
        self.assertIn("<PHONE_NUMBER>", result)
        print("✅ SANIT-4 PASSED — Multiple PII entities redacted together")
        print("   Raw    :", raw)
        print("   Cleaned:", result)

    def test_sanit_5_agent3_real_world_prompt_shape(self):
        raw = (
            "Patient John Smith with Type 2 Diabetes, Hypertension taking "
            "Metformin 500mg, Lisinopril 10mg should rest and monitor blood pressure. "
            "Contact john.smith@hospital.dk if symptoms worsen."
        )

        user_prompt = (
            "Triage summary: chest tightness and mild dizziness\n"
            "Patient chronic diseases: Type 2 Diabetes, Hypertension\n"
            "Current medications: Metformin 500mg, Lisinopril 10mg\n\n"
            "Medical guideline context: Follow-up and home monitoring guidance.\n\n"
            "Follow-up answers: It started yesterday and gets worse when walking.\n\n"
            "Please provide self-care advice."
        )

        with patch("utils.urllib.request.urlopen", return_value=make_mock_response(raw)):
            result = call_llm(
                "You are a medical assistant providing self-care advice.",
                user_prompt,
                analyzer=self.analyzer,
                anonymizer=self.anonymizer
            )

        self.assertNotIn("John Smith", result)
        self.assertNotIn("john.smith@hospital.dk", result)
        self.assertIn("Type 2 Diabetes", result)
        self.assertIn("Hypertension", result)
        self.assertIn("Metformin", result)
        self.assertIn("Lisinopril", result)
        print("✅ SANIT-5 PASSED — Agent 3 prompt shape sanitized while clinical context preserved")
        print("   Raw    :", raw)
        print("   Cleaned:", result)

    def test_sanit_6_empty_response_is_handled(self):
        with patch("utils.urllib.request.urlopen", return_value=make_mock_response("")):
            result = call_llm(
                "sys",
                "user",
                analyzer=self.analyzer,
                anonymizer=self.anonymizer
            )

        self.assertEqual(result, "")
        print("✅ SANIT-6 PASSED — Empty model response handled safely")

    def test_sanit_7_no_sanitization_without_engines(self):
        raw = "Patient John Smith should rest at home."
        with patch("utils.urllib.request.urlopen", return_value=make_mock_response(raw)):
            result = call_llm("sys", "user")

        self.assertEqual(result, raw)
        print("✅ SANIT-7 PASSED — Backward compatibility preserved")


class TestLLMFailureBehavior(unittest.TestCase):
    """Failure-oriented tests for robustness analysis."""

    def test_fail_1_network_failure_surfaces_to_caller(self):
        with patch("utils.urllib.request.urlopen", side_effect=URLError("Connection refused")):
            with self.assertRaises(URLError):
                call_llm("sys", "user")
        print("✅ FAIL-1 PASSED — Network failure surfaces to caller")

    def test_fail_2_malformed_response_shape_surfaces_to_caller(self):
        with patch(
            "utils.urllib.request.urlopen",
            return_value=make_custom_json_response({"unexpected": "shape"})
        ):
            with self.assertRaises(KeyError):
                call_llm("sys", "user")
        print("✅ FAIL-2 PASSED — Malformed response shape surfaces to caller")

    def test_fail_3_non_json_response_surfaces_to_caller(self):
        bad = MagicMock()
        bad.read.return_value = b'not-json'
        bad.__enter__ = lambda s: s
        bad.__exit__ = MagicMock(return_value=False)

        with patch("utils.urllib.request.urlopen", return_value=bad):
            with self.assertRaises(json.JSONDecodeError):
                call_llm("sys", "user")
        print("✅ FAIL-3 PASSED — Non-JSON response surfaces to caller")


if __name__ == "__main__":
    print("\n" + "=" * 74)
    print("  call_llm() Advanced Mitigation Test Suite")
    print("  LLM as a Tool — Agent-to-Ollama Communication")
    print("=" * 74 + "\n")
    unittest.main(verbosity=0)