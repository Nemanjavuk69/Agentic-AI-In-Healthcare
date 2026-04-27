from utils import call_llm, retrieve_dept_context

# =========================
# Routing threshold
# Patients with triage score <= THRESHOLD go to Agent 2 (emergency)
# Patients with triage score >  THRESHOLD go to Agent 3 (follow-up)
# Change this number to adjust routing behaviour
# =========================

TRIAGE_THRESHOLD = 2


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
# Uses retrieved DEPT context to assign a triage color and score
# =========================

def triage_agent(user_input: str) -> dict:
    dept_context = retrieve_dept_context(user_input)

    system_prompt = """
You are a medical triage assistant trained on Danish DEPT (Danish Emergency Process Triage) guidelines.

You will receive:
1. A patient's symptom description
2. Relevant excerpts from the official DEPT triage guidelines

Your job is to:
1. Write 2-3 sentences explaining your assessment of the symptoms based on the DEPT guidelines.
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
{user_input}

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
        "symptoms": user_input
    }


# =========================
# Step 3: Routing
# =========================

def route(triage_result: dict):
    score = triage_result["score"]
    symptoms = triage_result["symptoms"]
    response = triage_result["response"]

    print(f"\nAssistant: {response}\n")

    if score is None:
        print("Could not determine triage score. Please try again.\n")
        return

    if score <= TRIAGE_THRESHOLD:
        print(f"--- Triage score {score} is critical. Routing to Agent 2 (Emergency). ---\n")
        from agent2 import run_agent as run_agent2
        run_agent2(symptoms=symptoms, triage_score=score)
    else:
        print(f"--- Triage score {score}. Routing to Agent 3 (Follow-up). ---\n")
        from agent3 import run_agent as run_agent3
        triage_input = {
            "summary": symptoms,
            "urgency": response,
        }
        run_agent3(triage_input=triage_input, patient_id="P001")


# =========================
# Main interactive loop
# =========================

def main():
    print("=== DEPT Triage Assistant ===")
    print("Describe the patient's symptoms below, or type 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            print("Please enter a message.\n")
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        print("Analyzing...\n")

        if not is_symptom_input(user_input):
            print("Assistant: I am a medical triage assistant and can only assess medical symptoms. "
                  "Please describe the patient's symptoms — what they are feeling, "
                  "where it hurts, and how long it has been going on.\n")
            continue

        triage_result = triage_agent(user_input)
        route(triage_result)


if __name__ == "__main__":
    main()
