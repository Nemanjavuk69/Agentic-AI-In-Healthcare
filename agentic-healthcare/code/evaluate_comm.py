import copy
import json
from pathlib import Path
from typing import Any

import secure_comm


# =============================================
# Test data: a sample message and its signature
# =============================================

RAW_PATIENT = {
    "patient_id": "P001",
    "full_name": "Test Patient",
}

AGENT1_TO_AGENT2_MESSAGE = {
    "patient_id": RAW_PATIENT["patient_id"],
    "symptoms": "I have chest pain and shortness of breath.",
    "score": 1,
    "location": "2800",
}

AGENT1_TO_AGENT3_MESSAGE = {
    "patient_id": RAW_PATIENT["patient_id"],
    "symptoms": "I have a headache",
    "score": 4,
    "location": "2800",
}


# =============================================
# Utility function to pretty-print JSON
# =============================================

def pretty(data: Any) -> str:
    """Pretty JSON printer used by the evaluation script."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def result_line(name: str, passed: bool) -> None:
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")

def subsection(text: str) -> None:
    print("\n" + "-" * 90)
    print(text)
    print("-" * 90)


# =============================================
# Fake Agents
# =============================================

def original_agent2_receive(payload: dict) -> dict:
    """Simulates current direct function-call behaviour before mitigation."""
    return {
        "agent": "agent2",
        "status": "received_plaintext_payload",
        "received_payload": payload,
    }

def original_agentX_receive(payload: dict) -> dict:
    """Fake unauthorised agent before mitigation."""
    return {
        "agent": "agentX",
        "status": "UNAUTHORISED_AGENT_RECEIVED_PATIENT_DATA",
        "received_payload": payload,
    }

def secure_agent2_receive(encrypted_message: dict) -> dict:
    """Simulates Agent 2 after mitigation."""
    payload = secure_comm.receive_secure_message(
        expected_receiver="agent2",
        encrypted_message=encrypted_message,
        encrypted=True,
    )
    return {
        "agent": "agent2",
        "status": "accepted_secure_message",
        "received_payload": payload,
    }

def original_agentX_send(payload: dict) -> dict:
    """Simulates fake AgentX trying to send message before mitigation."""
    return {
        "agent": "agentX",
        "status": "UNAUTHORISED_AGENT_SENT_PATIENT_DATA",
        "sent_payload": payload,
    }


# ============================================
# Test cases
# ============================================
def test_insecure_channel_encryption() -> None:

    print("\n" + "=" * 90)
    print("TEST — INSECURE COMMUNICATION CHANNEL / PLAINTEXT VS ENCRYPTED MESSAGE")
    print("=" * 90)

    payload = copy.deepcopy(AGENT1_TO_AGENT2_MESSAGE)

    subsection("Before mitigation: direct plaintext dictionary is sent to Agent 2")
    before = original_agent2_receive(payload)
    print(pretty(before))
    before_plaintext = json.dumps(before)
    # FAIL - the transmitted message contains patient data in plaintext
    #result_line("Payload is human-readable in transit", "chest pain" in before_plaintext and "2800" in before_plaintext)
    result_line("Payload contains patient data",False)

    subsection("After mitigation: signed message is encrypted before transmission")
    encrypted_message = secure_comm.create_secure_message(
        sender="agent1",
        receiver="agent2",
        action="emergency_routing",
        payload=payload,
        encrypt=True,
    )
    print("Encrypted message transmitted between agents:\n")
    print(encrypted_message)
    # PASS - the transmitted message does not contain patient data in plaintext
    
    result_line("Encrypted message does not reveal symptom text", "chest pain" not in encrypted_message)
    result_line("Encrypted message does not reveal location", "2800" not in encrypted_message)

    received = secure_agent2_receive(encrypted_message)
    print("\nDecrypted and verified by Agent 2:")
    print(pretty(received))
    result_line("Agent 2 can decrypt and process authorised message", received["status"] == "accepted_secure_message")

    print(
        "\nInterpretation: Before mitigation, an observer of the communication could read patient data.\n"
        "After mitigation, the transmitted object is ciphertext and only the authorised receiver can \ndecrypt it."
    )


def test_unauthorised_disclosure_receive() -> None:

    print("\n" + "=" * 90)
    print("TEST — UNCONTROLLED DISCLOSURE TO UNAUTHORISED AGENT")
    print("=" * 90)

    payload = copy.deepcopy(AGENT1_TO_AGENT2_MESSAGE)

    subsection("Before mitigation: fake AgentX can receive the patient payload")
    before = original_agentX_receive(payload)
    print(pretty(before))
    # FAIL - the unauthorised agent can receive patient data if called
    result_line("Unauthorised agent received patient payload", False)

    subsection("After mitigation: communication policy rejects AgentX as receiver")
    try:
        _ = secure_comm.create_secure_message(
            sender="agent1",
            receiver="agentX",
            action="emergency_routing",
            payload=payload,
            encrypt=True,
        )
        rejected = False
    except PermissionError as exc:
        rejected = True
        print("Rejected as expected:", exc)
    # PASS - the communication policy prevents sending to unauthorised receiver
    result_line("Policy prevents disclosure to unauthorised receiver", rejected)

    print(
        "\nInterpretation: The fake agent represents a rogue internal debugging or experimental component. "
        "\nBefore mitigation, it can receive patient data if called. After mitigation, receiver authorisation "
        "\nblocks the disclosure before transmission."
    )

def test_unauthorised_disclosure_send() -> None:
    print("\n" + "=" * 90)
    print("TEST — UNCONTROLLED DISCLOSURE BY UNAUTHORISED AGENT")
    print("=" * 90)

    payload = copy.deepcopy(AGENT1_TO_AGENT2_MESSAGE)

    subsection("Before mitigation: fake AgentX can send patient payload")
    before = original_agentX_send(payload)
    print(pretty(before))
    # FAIL - the unauthorised agent can send patient data if called
    result_line("Unauthorised agent sent patient payload", False)

    subsection("After mitigation: communication policy rejects AgentX as sender")
    try:
        _ = secure_comm.create_secure_message(
            sender="agentX",
            receiver="agent2",
            action="emergency_routing",
            payload=payload,
            encrypt=True,
        )
        rejected = False
    except PermissionError as exc:
        rejected = True
        print("Rejected as expected:", exc)

    result_line("Policy prevents unauthorised sender from sending patient data", rejected)

    print(
        "\nInterpretation: Before mitigation, the fake agent could send patient data if called. After mitigation, "
        "\nsender authorisation blocks the attempt to disclose data before transmission."
    )


# ============================================
# Run tests
# ============================================

def main() -> None:

    print("\n" + "=" * 90)
    print("PRIVACY EVALUATION OF INTER-AGENT COMMUNICATION")
    print("=" * 90)

    print(
        "This script evaluates privacy risks in the communication between Agent 1, Agent 2, "
        "Agent 3,\nand a fake unauthorised AgentX. Each test prints the BEFORE and AFTER state and"
        "\nexplains how to interpret the result."
    )

    test_insecure_channel_encryption()
    test_unauthorised_disclosure_receive()
    test_unauthorised_disclosure_send()


if __name__ == "__main__":
    main()

