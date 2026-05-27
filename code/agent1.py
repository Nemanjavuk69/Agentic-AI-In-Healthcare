import json
import os
import random
import logging
from utils import call_llm, retrieve_dept_context, setup_analyzer_and_anonymizer, tokenize_patient, anonymize_text, sanitize_age, sanitize_cpr, sanitize_name, sanitize_free_text, sanitize_postal_code
from reset_log import reset
from secure_comm import create_secure_message

from patient_db_encryption import get_patient_db_cache, update_patient_in_cache

# =========================
# Routing threshold
# Patients with triage score <= THRESHOLD go to Agent 2 (emergency)
# Patients with triage score >  THRESHOLD go to Agent 3 (follow-up)
# Change this number to adjust routing behaviour
# =========================

os.environ["TQDM_DISABLE"] = "1" # disable tqdm progress bars in any libraries
logging.getLogger().setLevel(logging.WARNING)

# ─── Logging ──────────────────────────────────────────────────────────[...]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("agent1.log"),
        #logging.StreamHandler(),
    ],
)

# Add these lines to silence Presidio's INFO and WARNING logs:
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
logging.getLogger("presidio-anonymizer").setLevel(logging.ERROR)


log = logging.getLogger("agent1")

# ─── Config ───────────────────────────────────────────────────────────[...]

TRIAGE_THRESHOLD = 2

PATIENT_DB_DIR = os.path.join(os.path.dirname(__file__), "patient_db")
HOSPITAL_NAME  = "Aalborg University Hospital"


# =========================
# EHR helpers
# Load patient records and format them for the LLM
# =========================



# def save_patient_profile(patient: dict):
#     """Save updated patient profile."""
#     path = os.path.join(PATIENT_DB_DIR, f"{patient['patient_id']}.json")
#     with open(path, "w", encoding="utf-8") as f:
#         json.dump(patient, f, indent=2, ensure_ascii=False)

# Replace save_patient_profile()
def save_patient_profile(patient: dict):
    """Save patient to encrypted database."""
    update_patient_in_cache(patient['patient_id'], patient)



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
- "I broke my leg"
- "I broke my finger"
- "I fell and hit my head"

Examples of NON-symptom input:
- "Hello"
- "What can you help me with?"
- "Who are you?"

Respond with ONLY one word: YES or NO.
"""
    user_prompt = f"Does this message contain medical symptoms?\n\n\"{user_input}\""
    
    # log.info("=== SYMPTOM CLASSIFIER ===")
    # log.info("Input: %s", user_input)
    # log.info("Full prompt sent to LLM: %s", user_prompt)

    # Removed so we don't log the actual user input
    log.info("Symptom classifier invoked")

    result = call_llm(system_prompt, user_prompt).strip().upper()
    # log.info("Classifier result: %s", result)

    return result.startswith("YES")


# =========================
# Step 2: Triage Agent
# Uses retrieved DEPT context to assign a triage score
# =========================

def triage_agent(user_input: str) -> dict:
    dept_context = retrieve_dept_context(user_input)

    system_prompt = f"""
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
    # log.info("=== TRIAGE AGENT CALLED ===")
    # log.info("Patient symptoms: %s", user_input)
    log.info("Triage assessment in progress")

    response = call_llm(system_prompt, user_prompt)

    log.info("Triage response received")
    # log.info("Raw LLM Response:\n%s", response)

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

        # encrypt and sign the message for Agent 2
        encrypted_message_2 = create_secure_message(
            sender="agent1",
            receiver="agent2",
            action="emergency_routing",
            payload=emergency_data
        )

        result = run_agent2(encrypted_message_2)

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
            "patient_id": subject_id,
            "summary": symptoms,
            "urgency": response
        }

        # encrypt and sign the message for Agent 3
        encrypted_message_3 = create_secure_message(
            sender="agent1",
            receiver="agent3",
            action="follow_up",
            payload=triage_input
        )


        run_agent3(triage_input=encrypted_message_3)


# def load_patient(patient_id: str) -> dict:
#     """Load patient from encrypted database."""
#     path = os.path.join(PATIENT_DB_DIR, f"{patient_id}.json")
#     if not os.path.exists(path):
#         print("Patient file not found. Using default empty record.")
#         return {"patient_id": patient_id, "name": "", "age": None, "gender": "","chronic_diseases": [],
#                 "medications": [], "allergies": [], "hospital": HOSPITAL_NAME}
#     with open(path, "r") as f:
#         data = json.load(f)
#     return data

def load_patient(patient_id: str) -> dict:
    """Load patient from encrypted database."""
    db = get_patient_db_cache()
    if patient_id not in db:
        log.warning("Patient not found: %s", patient_id)
        return {"patient_id": patient_id, "name": "", "age": None, "gender": "","chronic_diseases": [],
                "medications": [], "allergies": [], "hospital": HOSPITAL_NAME}
    return db[patient_id]



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

    from reset_log import reset
    reset()

    analyzer, anonymizer = setup_analyzer_and_anonymizer()

    # Collect Real PII upfront (CPR and Name)

    cpr = ""
    while not cpr:
        try:
            raw_cpr = input("\nPlease enter the patient's CPR: ")
            cpr = sanitize_cpr(raw_cpr)
        except ValueError as e:
            print(f"Error: {e}")


    name = ""
    while not name:
        try:
            raw_name = input("Enter patient's full name: ").strip()
            name = sanitize_name(raw_name)
        except ValueError as e:
            print(f"Error: {e}")



    # Tokenize immediately. 
    # 'subject_id' is now a synthetic token 
    subject_id = tokenize_patient(cpr, name)
    print(f"\n[System] Patient mapped to secure internal ID: {subject_id}")



    # Load the medical profile using the TOKEN
    patient = load_patient(subject_id)

    # Ask for missing basic clinical information 
    updated = False

    if not patient.get("age"):
        while True:
            try:
                age_str = input(f"Enter patient's age: ").strip()
                patient["age"] = sanitize_age(age_str)
                updated = True
                break
            except ValueError as e:
                print(f"Error: {e}")
                patient["age"] = None

    if not patient.get("gender"):
        while True:
            gender = input("Enter patient's gender (male/female/other): ").strip().lower()
            if gender in ["male", "female", "other"]:
                patient["gender"] = gender
                updated = True
                break
            print("Invalid gender. Please enter 'male', 'female', or 'other'.")

    
    # save profile if we got any new info
    if updated:
        save_patient_profile(patient)
        print("Patient profile updated.\n")

    # handle postal code
    postal_code = ""
    while not postal_code:
        try:
            raw_postal_code = input("Enter patient's postal code: ").strip()
            postal_code = sanitize_postal_code(raw_postal_code)
        except ValueError as e:
            print(f"Error: {e}")

    # Ask for chronic diseases
    if not patient.get("chronic_diseases"):
        raw_chronic = input("Enter patient's chronic diseases (comma-separated, or press Enter if none): ").strip()
        if raw_chronic:
            patient["chronic_diseases"] = [item.strip() for item in raw_chronic.split(",")]
            updated = True
        else:
            patient["chronic_diseases"] = []

    # Ask for medications
    if not patient.get("medications"):
        raw_meds = input("Enter patient's medications (comma-separated, or press Enter if none): ").strip()
        if raw_meds:
            patient["medications"] = [item.strip() for item in raw_meds.split(",")]
            updated = True
        else:
            patient["medications"] = []

    # Ask for allergies
    if not patient.get("allergies"):
        raw_allergies = input("Enter patient's allergies (comma-separated, or press Enter if none): ").strip()
        if raw_allergies:
            patient["allergies"] = [item.strip() for item in raw_allergies.split(",")]
            updated = True
        else:
            patient["allergies"] = []


    print("\n" + "─" * 85)

    print("\nPlease describe the patient's symptoms below, or type 'quit' to exit.\n")

    while True:
        raw_user_input = input("You: ").strip()

        if not raw_user_input:
            print("Please enter a message.\n")
            continue
        if raw_user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        sanitized_input = sanitize_free_text(raw_user_input)

        
        user_input = anonymize_text(sanitized_input, analyzer=analyzer, anonymizer=anonymizer)

        print("\n" + "─" * 85)
        print("\nAnalyzing...\n")

        if not is_symptom_input(user_input):
            print("Assistant: I am a medical triage assistant and can only assess medical symptoms. "
                  "Please describe the patient's symptoms — what they are feeling, "
                  "where it hurts, and how long it has been going on.\n")
            continue

        triage_result = triage_agent(user_input)
        # log.info("Final triage score: %s", triage_result.get('score'))
        # log.info("Triage response: %s", triage_result.get('response'))
        log.info("Triage score assigned: %s", triage_result.get('score'))
        
        print(f"Triage assessment complete. Triage score: {triage_result['score']}")
        route(triage_result, subject_id, postal_code)
        print("Case handled. Closing system...")

        #Break after one case for demo purposes
        break

if __name__ == "__main__":
    main()
