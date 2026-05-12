import json
import os
import random
import logging
from utils import call_llm, retrieve_dept_context
from reset_log import reset

# =========================
# Routing threshold
# Patients with triage score <= THRESHOLD go to Agent 2 (emergency)
# Patients with triage score >  THRESHOLD go to Agent 3 (follow-up)
# Change this number to adjust routing behaviour
# =========================

os.environ["TQDM_DISABLE"] = "1" # disable tqdm progress bars in any libraries
logging.getLogger().setLevel(logging.WARNING)

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("agent1.log"),
        #logging.StreamHandler(),
    ],
)
log = logging.getLogger("agent3")

# ─── Config ───────────────────────────────────────────────────────────────────

TRIAGE_THRESHOLD = 2
TRIAGE_JSON = "triage.json"

PATIENT_DB_DIR = os.path.join(os.path.dirname(__file__), "patient_db")
HOSPITAL_NAME  = "Aalborg University Hospital"


# =========================
# EHR helpers
# Load past visits from triage.json and format them for the LLM
# =========================

def load_patient(patient_id: str) -> dict:
    """Load patient record from its JSON file."""
    path = os.path.join(PATIENT_DB_DIR, f"{patient_id}.json")
    if not os.path.exists(path):
        print("Patient file not found. Using default empty record.")
        return {"patient_id": patient_id, "name": "", "age": None, "gender": "","chronic_diseases": [],
                "medications": [], "allergies": [], "hospital": HOSPITAL_NAME}
    with open(path, "r") as f:
        data = json.load(f)
    return data

def save_patient_profile(patient: dict):
    """Save updated patient profile."""
    path = os.path.join(PATIENT_DB_DIR, f"{patient['patient_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(patient, f, indent=2, ensure_ascii=False)

def load_past_visits(subject_id: str) -> list[dict]:
    """Return all records from triage.json matching the given subject_id."""
    if not os.path.exists(TRIAGE_JSON):
        return []
    with open(TRIAGE_JSON, encoding="utf-8") as f:
        records = json.load(f)
    return [r for r in records if str(r.get("subject_id", "")) == str(subject_id)]


def format_visits_for_prompt(visits: list[dict]) -> str:
    """Convert past visit records into a readable summary for the LLM."""
    if not visits:
        return "No previous visits on record. This is the patient's first visit."
    lines = []
    for i, v in enumerate(visits, 1):
        lines.append(
            f"  Visit {i}: chief complaint='{v.get('chiefcomplaint', 'N/A')}', "
            f"acuity={v.get('acuity', 'N/A')}, "
            f"HR={v.get('heartrate', 'N/A')}, "
            f"temp={v.get('temperature', 'N/A')}, "
            f"O2sat={v.get('o2sat', 'N/A')}, "
            f"SBP/DBP={v.get('sbp', 'N/A')}/{v.get('dbp', 'N/A')}, "
            f"pain={v.get('pain', 'N/A')}"
        )
    return "\n".join(lines)


def append_visit(subject_id: str, symptoms: str, score: int | None):
    """
    Append a new triage record to triage.json after a session completes.
    Only fills fields that are available — leaves others blank to match the
    existing schema: subject_id, stay_id, temperature, heartrate, resprate,
    o2sat, sbp, dbp, pain, acuity, chiefcomplaint
    """
    record = {
        "subject_id":    str(subject_id),
        "stay_id":       str(random.randint(10_000_000, 99_999_999)),
        "temperature":   "",
        "heartrate":     "",
        "resprate":      "",
        "o2sat":         "",
        "sbp":           "",
        "dbp":           "",
        "pain":          "",
        "acuity":        str(score) if score is not None else "",
        "chiefcomplaint": symptoms[:200]   # cap length for safety
    }

    records = []
    if os.path.exists(TRIAGE_JSON):
        with open(TRIAGE_JSON, encoding="utf-8") as f:
            records = json.load(f)

    records.append(record)

    with open(TRIAGE_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    print(f"\n[System] Visit appended to {TRIAGE_JSON} "
          f"(subject_id={subject_id}, stay_id={record['stay_id']})\n")


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
    
    log.info("=== SYMPTOM CLASSIFIER ===")
    log.info("Input: %s", user_input)
    log.info("Full prompt sent to LLM: %s", user_prompt)

    result = call_llm(system_prompt, user_prompt).strip().upper()
    log.info("Classifier result: %s", result)

    return result.startswith("YES")


# =========================
# Step 2: Triage Agent
# Uses retrieved DEPT context and past visit history to assign a triage score
# =========================

def triage_agent(user_input: str, visit_history: str) -> dict:
    dept_context = retrieve_dept_context(user_input)

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
{user_input}

Relevant DEPT guidelines:
{dept_context}
"""
    log.info("=== TRIAGE AGENT CALLED ===")
    log.info("Patient symptoms: %s", user_input)
    log.info("Visit history length: %d", len(visit_history))

    response = call_llm(system_prompt, user_prompt)

    log.info("Raw LLM Response:\n%s", response)

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

def route(triage_result: dict, subject_id: str, postal_code: str):
    score    = triage_result["score"]
    symptoms = triage_result["symptoms"]
    response = triage_result["response"]

    #print(f"\nAssistant: {response}\n")

    # Always append the visit to the EHR, regardless of routing outcome
    append_visit(subject_id, symptoms, score)

    if score is None:
        print("Could not determine triage score. Please try again.\n")
        return

    if score <= TRIAGE_THRESHOLD:

        print(f"Triage score {score} is critical. Routing to Agent 2 (Emergency Response Team).")
        from agent2 import run_agent as run_agent2
        #run_agent2(symptoms=symptoms, triage_score=score)
        emergency_data = {
        "patient_id": subject_id,
        "symptoms": symptoms,
        "score": score,
        "location": postal_code
    }
        result = run_agent2(emergency_data)

        if isinstance(result, dict):
            print(f"\nMessage: {result.get('message', 'N/A')}")
            print(f"Hospital: {result.get('hospital', 'N/A')}")
            print(f"Department: {result.get('department', 'N/A')}")
            print(f"Address: {result.get('address', 'N/A')}")
            if result.get('transport'):
                print(f"Transport: {result.get('transport').upper()}")
        else:
            print(result)

        
    else:
        print(f"Triage score {score}. Routing to Agent 3 (Medical Follow-up).\n")
        print("\n" + "─" * 85)
        from agent3 import run_agent as run_agent3
        triage_input = {
            "summary": symptoms,
            "urgency": response
        }
        run_agent3(triage_input=triage_input, patient_id=subject_id)


# =========================
# Main interactive loop
# =========================

def main():
    print("\n" + "=" * 85)
    print(" " * 28 + "DEPT TRIAGE ASSISTANT")
    print("\n" + "=" * 85)
    print("""\nWelcome to the DEPT Triage Assistant. 
        \nMy purpose is to quickly and accurately assess the urgency of medical complaints using the official Danish DEPT triage system.
        \nBased on the symptoms you describe, I will:
        \n- Determine the appropiate triage level
        \n- Route critical cases directly to emergency services
        \n- Provide follow-up advice for less urgent cases
          """)
    
    print("\n" + "─" * 85)

    reset()


    # Ask for subject_id before anything else, keep prompting until we get a value
    subject_id = ""
    while not subject_id:
        subject_id = input("\nPlease enter the patient's subject ID: ").strip()
        if not subject_id:
            print("Subject ID cannot be empty. Please try again.")

    patient = load_patient(subject_id)

    # Ask for missing basic information
    updated = False

    if not patient.get("name"):
        patient["name"] = input(f"Enter patient's full name: ").strip()
        updated = True

    if not patient.get("age"):
        try:
            age_str = input(f"Enter patient's age: ").strip()
            patient["age"] = int(age_str) if age_str else None
            updated = True
        except:
            patient["age"] = None

    if not patient.get("gender"):
        gender = input("Enter patient's gender (male/female/other): ").strip().lower()
        patient["gender"] = gender if gender else ""
        updated = True
    
    # safe profile if we got any new info
    if updated:
        save_patient_profile(patient)
        print("Patient profile updated.\n")


    # handle postal code
    postal_code = ""
    while not postal_code:
        postal_code = input("\nPlease enter the patient's postal code: ").strip()
        if not postal_code:
            print("Postal code cannot be empty. Please try again.")



    past_visits = load_past_visits(subject_id)
    if past_visits:
        print(f"\n[System] Found {len(past_visits)} past visit(s) for subject {subject_id}.")
    else:
        print(f"[System] No previous visits found for subject {subject_id}. Treating as first visit.")

    visit_history = format_visits_for_prompt(past_visits)

    print("\n" + "─" * 85)

    print("\nPlease describe the patient's symptoms below, or type 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            print("Please enter a message.\n")
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        print("\n" + "─" * 85)
        print("\nAnalyzing...\n")

        if not is_symptom_input(user_input):
            print("Assistant: I am a medical triage assistant and can only assess medical symptoms. "
                  "Please describe the patient's symptoms — what they are feeling, "
                  "where it hurts, and how long it has been going on.\n")
            continue

        triage_result = triage_agent(user_input, visit_history)
        log.info("Final triage score: %s", triage_result.get('score'))
        log.info("Triage response: %s", triage_result.get('response'))
        
        print(f"Triage assessment complete. Triage score: {triage_result['score']}")
        route(triage_result, subject_id,postal_code)
        print("Case handled. Closing system...")

        #Break after one case for demo purposes
        break


if __name__ == "__main__":
    main()
