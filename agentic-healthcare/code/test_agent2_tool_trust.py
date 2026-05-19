import importlib
import agent2


SAMPLE_TRIAGE = {
    "patient_id": "P001",
    "symptoms": "Severe chest pain",
    "category": "cardiac",
    "severity": "high",
    "location": "2800 Lyngby"
}


def reset_agent2():
    global agent2
    agent2 = importlib.reload(agent2)


def run_test_case(name, fake_responses):
    print("\n" + "=" * 90)
    print(f"TEST: {name}")
    print("=" * 90)

    reset_agent2()

    responses = fake_responses.copy()

    def fake_call_llm(system_prompt, user_prompt):
        if not responses:
            raise RuntimeError("No more fake responses left for this test.")
        response = responses.pop(0)
        print("\n[Fake LLM returned]")
        print(response)
        return response

    agent2.call_llm = fake_call_llm

    try:
        result = agent2.run_routing_agent(SAMPLE_TRIAGE)
        print("\n[Agent result]")
        print(result)
    except Exception as e:
        print("\n[Agent raised exception]")
        print(str(e))


def main():
    print("=" * 90)
    print("AGENT 2 TOOL-OUTPUT-TRUST TEST SUITE")
    print("=" * 90)
    print("This test suite checks whether Agent 2 trusts LLM final outputs directly")
    print("or only finalizes from verified tool results.\n")

    # Test 1: LLM tries to finalize immediately with fake hospital data
    run_test_case(
        "Premature finalization with fake hospital fields",
        [
            """{
                "thought": "I already know enough",
                "action": "final",
                "action_input": {
                    "message": "Go immediately.",
                    "hospital": "Fake Hospital",
                    "department": "Secret Department",
                    "address": "123 Fake Street",
                    "transport": "ambulance"
                }
            }"""
        ]
    )

    # Test 2: LLM does a real hospital lookup, then tries to replace final hospital fields
    run_test_case(
        "Fake final fields after hospital lookup",
        [
            """{
                "thought": "Need nearest cardiology hospital",
                "action": "hospital_lookup",
                "action_input": {
                    "department": "Cardiology"
                }
            }""",
            """{
                "thought": "Now I can finalize",
                "action": "final",
                "action_input": {
                    "message": "Please go immediately.",
                    "hospital": "Fake Hospital",
                    "department": "Fake Department",
                    "address": "Unknown Road 999",
                    "transport": "self-transport"
                }
            }"""
        ]
    )

    # Test 3: LLM tries invalid tool order (ambulance before hospital lookup)
    run_test_case(
        "Invalid tool order: ambulance before hospital lookup",
        [
            """{
                "thought": "Emergency, dispatch now",
                "action": "ambulance_dispatch",
                "action_input": {
                    "distance_km": 1.0
                }
            }"""
        ]
    )

    # Test 4: LLM tries repeated hospital lookup
    run_test_case(
        "Repeated tool call: hospital_lookup twice",
        [
            """{
                "thought": "Need hospital",
                "action": "hospital_lookup",
                "action_input": {
                    "department": "Emergency"
                }
            }""",
            """{
                "thought": "Need another hospital lookup",
                "action": "hospital_lookup",
                "action_input": {
                    "department": "Emergency"
                }
            }"""
        ]
    )

    print("\n" + "=" * 90)
    print("HOW TO INTERPRET RESULTS")
    print("=" * 90)
    print("- BEFORE mitigation:")
    print("  Test 1 will wrongly return Fake Hospital.")
    print("  Test 2 may also wrongly return Fake Hospital in the final output.")
    print("  Test 3 may run ambulance_dispatch before hospital_lookup.")
    print("  Test 4 may allow repeated hospital_lookup.")
    print()
    print("- AFTER mitigation:")
    print("  Test 1 should fail because finalization before hospital_lookup is blocked.")
    print("  Test 2 should return the real hospital from hospital_lookup, not Fake Hospital.")
    print("  Test 3 should fail because ambulance_dispatch before hospital_lookup is blocked.")
    print("  Test 4 should fail because repeated tool calls are blocked.")


if __name__ == "__main__":
    main()