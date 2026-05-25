import importlib
import json
import agent2


def reset_agent2():
    global agent2
    agent2 = importlib.reload(agent2)


def make_fake_call_llm(responses):
    queue = responses.copy()

    def fake_call_llm(system_prompt, user_prompt):
        if not queue:
            raise RuntimeError("No more fake responses left for this test.")
        return queue.pop(0)

    return fake_call_llm


def run_case(name, triage, fake_responses, assertion_fn):
    reset_agent2()
    agent2.call_llm = make_fake_call_llm(fake_responses)

    try:
        result = agent2.run_routing_agent(triage)
        passed, detail = assertion_fn(result)
    except Exception as e:
        result = str(e)
        passed, detail = False, result

    status = "PASS" if passed else "FAIL"
    print(f"{status:<6} | {name}")
    if not passed:
        print(f"       Result: {result}")
        print(f"       Detail: {detail}")


def is_final_response(result):
    return isinstance(result, dict) and "hospital" in result and "transport" in result


def main():
    print("=" * 100)
    print("AGENT 2 TOOL TRUST + PRIVACY TEST SUITE")
    print("=" * 100)

    sample_score_2 = {
        "patient_id": "P001",
        "symptoms": "Severe chest pain but able to walk",
        "category": "cardiac",
        "severity": "high",
        "score": 2,
        "location": "2800 Lyngby",
    }

    sample_score_1 = {
        "patient_id": "P002",
        "symptoms": "Crushing chest pain and collapse",
        "category": "cardiac",
        "severity": "critical",
        "score": 1,
        "location": "2100 København Ø",
    }

    sample_score_2_immobile = {
        "patient_id": "P003",
        "symptoms": "Severe leg injury, cannot walk or move",
        "category": "trauma",
        "severity": "high",
        "score": 2,
        "location": "2650 Hvidovre",
    }

    run_case(
        "Premature final blocked",
        sample_score_2,
        [
            json.dumps({
                "thought": "I already know enough",
                "action": "final",
                "action_input": {
                    "message": "Go immediately.",
                    "hospital": "Fake Hospital"
                }
            }),
            json.dumps({
                "thought": "Now finalize correctly",
                "action": "final",
                "action_input": {
                    "message": "Please go to the selected hospital."
                }
            }),
        ],
        lambda result: (
            is_final_response(result) and result["hospital"] != "Fake Hospital",
            "Final response should come from trusted hospital lookup, not fake LLM fields."
        )
    )

    run_case(
        "Fake final hospital fields ignored",
        sample_score_2,
        [
            json.dumps({
                "thought": "Need nearest cardiology hospital",
                "action": "hospital_lookup",
                "action_input": {"department": "Cardiology"}
            }),
            json.dumps({
                "thought": "Finalize with invented values",
                "action": "final",
                "action_input": {
                    "message": "Please go immediately.",
                    "hospital": "Fake Hospital",
                    "department": "Fake Department",
                    "address": "Unknown Road 999",
                    "transport": "ambulance"
                }
            }),
        ],
        lambda result: (
            is_final_response(result)
            and result["hospital"] != "Fake Hospital"
            and result["address"] != "Unknown Road 999",
            "Trusted tool results should override fake LLM final fields."
        )
    )

    run_case(
        "Ambulance before lookup blocked or overridden",
        sample_score_2,
        [
            json.dumps({
                "thought": "Dispatch now",
                "action": "ambulance_dispatch",
                "action_input": {"distance_km": 1.0}
            }),
            json.dumps({
                "thought": "Finalize",
                "action": "final",
                "action_input": {"message": "Proceed to hospital."}
            }),
        ],
        lambda result: (
            is_final_response(result),
            "Agent should force hospital_lookup before finalization."
        )
    )

    run_case(
        "Repeated hospital lookup not trusted blindly",
        sample_score_2,
        [
            json.dumps({
                "thought": "Need hospital",
                "action": "hospital_lookup",
                "action_input": {"department": "Emergency"}
            }),
            json.dumps({
                "thought": "Need another lookup",
                "action": "hospital_lookup",
                "action_input": {"department": "Emergency"}
            }),
        ],
        lambda result: (
            result == "Agent stopped (max steps reached)" or is_final_response(result) or "repeated" in str(result).lower(),
            "Repeated tool calls should not run unsafely."
        )
    )

    reset_agent2()
    raw_history = [
        {
            "thought": "lookup",
            "action": "hospital_lookup",
            "result": {
                "hospital": "Rigshospitalet",
                "department": "Cardiology",
                "coords": (55.695, 12.566),
                "address": "Blegdamsvej 9, 2100 København Ø",
                "distance_km": 5.2,
            },
        },
        {
            "thought": "dispatch",
            "action": "ambulance_dispatch",
            "result": {
                "status": "dispatched",
                "eta_minutes": 7,
                "message": "Ambulance is on the way.",
            },
        },
    ]
    safe_history = agent2.build_safe_history(raw_history)
    privacy_pass = (
        "coords" not in str(safe_history).lower()
        and "Blegdamsvej" not in str(safe_history)
        and "message" not in str(safe_history).lower()
    )
    print(f"{'PASS' if privacy_pass else 'FAIL':<6} | Safe history minimizes raw tool outputs")

    run_case(
        "Score 1 always dispatches ambulance",
        sample_score_1,
        [
            json.dumps({
                "thought": "Need hospital first",
                "action": "hospital_lookup",
                "action_input": {"department": "Emergency"}
            }),
            json.dumps({
                "thought": "Now finalize",
                "action": "final",
                "action_input": {"message": "Emergency response initiated."}
            }),
            json.dumps({
                "thought": "Now finalize after dispatch",
                "action": "final",
                "action_input": {"message": "Emergency response initiated."}
            }),
        ],
        lambda result: (
            is_final_response(result)
            and result["transport"] == "ambulance"
            and "ambulance" in result["message"].lower(),
            "Score 1 must produce ambulance transport and communicate ETA/dispatch."
        )
    )

    run_case(
        "Score 2 defaults to self-transport",
        sample_score_2,
        [
            json.dumps({
                "thought": "Need hospital",
                "action": "hospital_lookup",
                "action_input": {"department": "Cardiology"}
            }),
            json.dumps({
                "thought": "Finalize with self transport",
                "action": "final",
                "action_input": {"message": "Please proceed safely to the hospital."}
            }),
        ],
        lambda result: (
            is_final_response(result) and result["transport"] == "self-transport",
            "Score 2 should default to self-transport when the patient can move."
        )
    )

    run_case(
        "Score 2 + immobility triggers ambulance",
        sample_score_2_immobile,
        [
            json.dumps({
                "thought": "Need nearest emergency hospital",
                "action": "hospital_lookup",
                "action_input": {"department": "Emergency"}
            }),
            json.dumps({
                "thought": "Finalize",
                "action": "final",
                "action_input": {"message": "Emergency transport required."}
            }),
            json.dumps({
                "thought": "Finalize after dispatch",
                "action": "final",
                "action_input": {"message": "Emergency transport required."}
            }),
        ],
        lambda result: (
            is_final_response(result)
            and result["transport"] == "ambulance",
            "Score 2 with inability to move should trigger ambulance."
        )
    )

    print("-" * 100)
    print("Interpretation:")
    print("- Trusted tool outputs should determine final hospital facts.")
    print("- Safe history should exclude coordinates, raw addresses in history summaries, and dispatch messages.")
    print("- Transport policy should be enforced by code, not only by the LLM prompt.")


if __name__ == "__main__":
    main()