import json
import os
from datetime import datetime
from typing import List, Dict, Optional

from utils import call_llm, retrieve_dept_context
from agent3 import (
    load_patient, 
    map_symptom_to_specialty, 
    tool_book_appointment, 
    tool_self_care_advice,
    QUESTION_SYSTEM,
    DECISION_SYSTEM,
    REFLECTION_SYSTEM,
    check_calendar
)

# =========================
# Non-Interactive Agent 3
# =========================

def run_followup_loop_non_interactive(
    triage_summary: str, 
    patient_id: str = "P004",
    max_turns: int = 3,                    # Reduced for red teaming speed
    simulated_answers: Optional[List[str]] = None
) -> Dict:
    """
    Non-interactive version of the follow-up questioning loop.
    """
    patient = load_patient(patient_id)
    history: List[Dict] = []
    answers: List[str] = simulated_answers or []

    turn = 0
    while turn < max_turns:
        history_text = ""
        for msg in history:
            role = "Assistant" if msg["role"] == "assistant" else "Patient"
            history_text += f"{role}: {msg['content']}\n"

        prompt = (
            f"Patient triage summary: {triage_summary}\n\n"
            f"Conversation so far:\n{history_text}\n"
            f"Do you need more information?."
        )

        response = call_llm(QUESTION_SYSTEM, prompt)

        try:
            data = json.loads(response)
        except:
            break

        if data.get("action") == "make_decision":
            break

        question = data.get("question", "Can you tell me more about your symptoms?")
        history.append({"role": "assistant", "content": question})

        # Use simulated answer or generate one
        if len(answers) > turn:
            answer = answers[turn]
        else:
            # Fallback: simulate a reasonable patient answer
            answer = call_llm(
                "You are a patient answering a doctor's question. Give a short, natural response.",
                f"Question: {question}\nGive a short answer:"
            )
            answers.append(answer)

        history.append({"role": "user", "content": answer})
        turn += 1

    return {
        "patient": patient,
        "answers": answers,
        "history": history,
        "triage_summary": triage_summary,
    }


def make_decision_non_interactive(context: Dict) -> Dict:
    """Uses your exact decision + reflection logic"""
    triage_summary = context["triage_summary"]
    answers = context["answers"]
    answers_text = "\n".join(answers)

    rag_query = f"{triage_summary} {answers_text}"
    rag_context = retrieve_dept_context(rag_query)

    decision_prompt = (
        f"Triage summary: {triage_summary}\n"
        f"Medical guideline context: {rag_context}\n\n"
        f"Follow-up answers:\n{answers_text}\n\n"
        "Make your decision now."
    )

    decision_raw = call_llm(DECISION_SYSTEM, decision_prompt)

    try:
        decision = json.loads(decision_raw)
    except:
        decision = {"decision": "appointment", "symptom_category": "general", "reasoning": "Fallback decision"}

    # Reflection
    reflection_prompt = f"""
Decision:
{json.dumps(decision, indent=2)}

Context:
Triage: {triage_summary}
Answers: {answers_text}
"""
    reflection_raw = call_llm(REFLECTION_SYSTEM, reflection_prompt)

    try:
        reflection = json.loads(reflection_raw)
        if reflection.get("status") == "revise":
            decision = {
                "decision": reflection["suggested_decision"],
                "symptom_category": decision.get("symptom_category", "general"),
                "reasoning": f"Revised: {reflection.get('reason', '')}"
            }
    except:
        pass

    return decision


def run_agent3_non_interactive(
    symptoms: str,
    patient_id: str = "TEST_PATIENT_001",
    simulated_answers: Optional[List[str]] = None
) -> Dict:
    """
    Full non-interactive Agent 3 pipeline.
    Very close to your original run_agent() logic.
    """
    triage_input = {
        "summary": symptoms,
        "urgency": "medium"
    }

    # Step 1: Follow-up loop (non-interactive)
    context = run_followup_loop_non_interactive(
        triage_summary=symptoms,
        patient_id=patient_id,
        simulated_answers=simulated_answers
    )

    # Step 2: Make decision
    decision_obj = make_decision_non_interactive(context)
    decision = decision_obj.get("decision", "appointment")
    category = decision_obj.get("symptom_category", "general")
    reasoning = decision_obj.get("reasoning", "No reasoning provided.")

    patient = context["patient"]
    follow_up_answers = context["answers"]

    # Step 3: Execute action (non-interactive - no user confirmation)
    if decision == "appointment":
        tool_result = tool_book_appointment(category, patient_id)
        output = {
            "action": "appointment",
            "booking": tool_result,
            "patient_id": patient_id,
            "reasoning": reasoning,
            "answers": follow_up_answers,
            "final_decision": decision_obj
        }
        final_message = f"Appointment booked for {category} specialty."
    else:
        tool_result = tool_self_care_advice(symptoms, patient, follow_up_answers)
        output = {
            "action": "self_care",
            "advice": tool_result,
            "patient_id": patient_id,
            "reasoning": reasoning,
            "answers": follow_up_answers,
            "final_decision": decision_obj
        }
        final_message = "Self-care advice provided."

    return {
        "final_message": final_message,
        "decision": decision,
        "category": category,
        "reasoning": reasoning,
        "full_output": output,
        "triage_summary": symptoms
    }


# For testing
if __name__ == "__main__":
    test_symptoms = "I have had a bad headache for 4 days with nausea."
    result = run_agent3_non_interactive(test_symptoms, simulated_answers=None)
    print("\n=== Agent 3 Non-Interactive Result ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))