import os
import json
from utils import call_llm, retrieve_dept_context
from agent1 import TRIAGE_THRESHOLD, load_past_visits, format_visits_for_prompt, append_visit

# =========================
# Step 1: Symptom Classifier
# =========================

def is_symptom_input(user_input: str) -> bool:
    system_prompt = """
You are a medical intake classifier.

Your only job is to decide if the user's message contains medical symptoms,
health complaints, or a description of how a patient is feeling physically or mentally.

Examples of symptom input:
- "My chest is burning"
- "I have had a headache for 3 days"
- "The patient is vomiting and has a fever"

Examples of NON-symptom input:
- "Hello"
- "What can you help me with?"
- "Who are you?"

Respond with ONLY one word: YES or NO.
"""
    user_prompt = f"Does this message contain medical symptoms?\n\n\"{user_input}\""

    result = call_llm(system_prompt, user_prompt).strip().upper()

    return result.startswith("YES")


# =========================
# Step 2: Triage Agent
# Uses retrieved DEPT context and past visit history to assign a triage score
# =========================

def triage_agent(symptoms: str, visit_history: str) -> dict:

    dept_context = retrieve_dept_context(symptoms)

    system_prompt = f"""
You are a medical triage assistant trained on Danish DEPT (Danish Emergency Process Triage) guidelines.

You will receive:
1. A patient's symptom description
2. Relevant excerpts from the official DEPT triage guidelines
3. The patient's past ED visit history

When assessing urgency, take the patient's history into account. For example, a patient with a
previous high-acuity visit for chest pain should be treated with extra caution if presenting
with similar symptoms again.

Patient history from previous ED visits:
{visit_history}

Your job is to:
1. Write 2-3 sentences explaining your assessment of the symptoms based on the DEPT guidelines
   and the patient's history.
2. Assign a triage color on this exact scale:
   - 1 RØD    - Immediately life-threatening
   - 2 ORANGE - Urgent, potentially life-threatening
   - 3 GUL    - Urgent but stable
   - 4 GRØN   - Less urgent
   - 5 BLÅ    - Non-urgent

Always end your response with this exact line and nothing after it:
Triage level: [NUMBER] [COLOR]

Example ending: Triage level: 2 ORANGE
"""

    user_prompt = f"""Patient symptoms:
{symptoms}

Relevant DEPT guidelines:
{dept_context}
"""

    response = call_llm(system_prompt, user_prompt)



    # Extract triage score from the last line
    score = None
    for line in response.splitlines():
        if line.strip().startswith("Triage level:"):
            try:
                score = int(line.strip().split()[2])
            except (IndexError, ValueError):
                pass

    return {
        "response": response,
        "score": score,
        "symptoms": symptoms
    }


# =========================
# Main interactive loop
# =========================

def main(symptoms:str, subject_id="P003", postal_code="2200") -> dict:
    print(f"[Agent1] Processing sympoms for patient for patient {subject_id}")

    
    past_visits = load_past_visits(subject_id)
    visit_history = format_visits_for_prompt(past_visits)
    if not is_symptom_input(symptoms):
        print("Assistant: I am a medical triage assistant and can only assess medical symptoms. "
                  "Please describe the patient's symptoms — what they are feeling, "
                 "where it hurts, and how long it has been going on.\n")


    triage_result = triage_agent(symptoms, visit_history)
    score = triage_result.get("score")
    response = triage_result.get("response")


    append_visit(subject_id, symptoms, score)

    if score is None:
        routing = "unknown"
        final_message = "Could not determine triage score"
    elif score <= TRIAGE_THRESHOLD:
        routing = "emergency (Agent 2)"
        final_message = f"Triage score {score} is critical. Routing to emergency services."
    else:
        routing = "follow-up (Agent 3)"
        final_message = f"Triage score {score}. Routing to medical follow-up."

    
    return {
        "triage_response": response,
        "triage_score": score,
        "routing": routing,
        "final_message": final_message,
        "subject_id": subject_id,
        "postal_code": postal_code
    }




if __name__ == "__main__":
    test_symptoms = "I have severe chest pain radiating to my left arm for the last 30 minutes."
    result=main(test_symptoms)
    print(json.dumps(result, indent=2, ensure_ascii=False))
