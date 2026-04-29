"""
Agent 3 – Medical Follow-Up & Decision Agent
Role: Receives triage output, asks follow-up questions, decides between
      booking an appointment or giving self-care advice, then calls the
      appropriate tool.

Multi-agent comms: stubs are marked with  # FUTURE: MQ/REST/gRPC
"""

import json
import logging
import os
from datetime import datetime
import requests
import re

from utils import call_llm, retrieve_dept_context

# you need to run ollama and run python fake_api.py in separate terminals

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("agent3.log"),
        #logging.StreamHandler(),
    ],
)
log = logging.getLogger("agent3")

# ─── Config ───────────────────────────────────────────────────────────────────

PATIENT_DB_DIR = os.path.join(os.path.dirname(__file__), "patient_db")
HOSPITAL_NAME  = "Aalborg University Hospital"

# Expanded specialty map
SPECIALTY_MAP = {
    "chest": "cardiology",
    "heart": "cardiology",
    "breath": "pulmonology",
    "cough": "pulmonology",
    "head": "neurology",
    "migraine": "neurology",
    "fracture": "orthopedics",
    "bone": "orthopedics",
    "skin": "dermatology",
    "rash": "dermatology",
    "diabetes": "endocrinology",
    "throat": "general",
    "fever": "general",
}

SYMPTOM_PATTERNS = {
    "cardiology": [
        r"chest pain",
        r"chest tightness",
        r"pressure in chest",
        r"heart pain",
        r"chest"
    ],
    "pulmonology": [
        r"shortness of breath",
        r"breathing difficulty",
        r"cannot breathe",
        r"cough",
        r"breath"
    ],
    "neurology": [
        r"headache",
        r"migraine",
        r"dizziness",
        r"head pain",
        r"head"
    ],
    "orthopedics": [
        r"fracture",
        r"broken bone",
        r"joint pain",
        r"bone"
    ],
    "dermatology": [
        r"rash",
        r"skin problem",
        r"itching",
        r"skin"
    ],
    "general": [
        r"fever",
        r"sore throat",
        r"fatigue",
        r"weakness"
    ]
}

# ─── Patient DB (JSON files) ──────────────────────────────────────────────────

def load_patient(patient_id: str) -> dict:
    """Load patient record from its JSON file."""
    path = os.path.join(PATIENT_DB_DIR, f"{patient_id}.json")
    if not os.path.exists(path):
        log.warning("Patient file not found: %s — using empty record", path)
        return {"patient_id": patient_id, "name": "Unknown", "chronic_diseases": [],
                "medications": [], "allergies": [], "hospital": HOSPITAL_NAME}
    with open(path, "r") as f:
        data = json.load(f)
    log.info("Loaded patient: %s", data)
    return data

# ─── Fake calendar ────────────────────────────────────────────────────────────

FAKE_CALENDAR = [
    "2025-06-10 09:30",
    "2025-06-10 11:00",
    "2025-06-11 14:00",
    "2025-06-12 08:30",
]

def check_calendar(specialty: str) -> str:
    """Step 5 – fake calendar lookup. Returns next available slot."""
    log.info("CALENDAR CHECK: looking for slot | specialty=%s", specialty)
    # change this
    slot = FAKE_CALENDAR[0]
    log.info("CALENDAR: next available slot = %s", slot)
    return slot

# ─── Tool 1: Appointment booking ─────────────────────────────────────────────

def is_negated(text, match_start):
    """Check if a match is negated by looking at previous 3 words"""
    window = text[max(0, match_start - 40):match_start]
    return any(neg in window for neg in ("no", "not", "don't", "doesn't", "without"))

def map_symptom_to_specialty(symptom: str) -> str:
    symptom = symptom.lower()
    scores = {}
    for specialty, patterns in SYMPTOM_PATTERNS.items():

        for pattern in patterns:
            for match in re.finditer(pattern, symptom):

                # skip negated mentions
                if is_negated(symptom, match.start()):
                    continue

                scores[specialty] = scores.get(specialty, 0) + 2  # strong signal

    # fallback: weak keyword matching
    for keyword, spec in SPECIALTY_MAP.items():
        if keyword in symptom:
            scores[spec] = scores.get(spec, 0) + 1

    if scores:
        # return the specialty with the most patterns
        return max(scores, key=scores.get)

    return "general"


def tool_book_appointment(symptom_category: str, patient_id: str) -> dict:
    """
    Books an appointment for the patient.
    Steps: load history → determine specialty → book at fixed hospital
           → fake API call → check calendar
    """
    log.info("TOOL CALL: book_appointment | patient=%s symptom=%s", patient_id, symptom_category)

    # Step 1 – load patient history
    patient = load_patient(patient_id)

    # Step 2 – determine specialty from symptom category
    specialty = map_symptom_to_specialty(symptom_category)
    log.info("Determined specialty: %s", specialty)
    
    # Step 3 – check calendar for next available slot
    time_slot = check_calendar(specialty)
    
    # Step 4 - book appointment: access to external API
    
    payload = {
        "hospital": HOSPITAL_NAME,
        "specialty": specialty,
        "time": time_slot,
        "patient_id": patient_id
    }
    
    log.info("Data sent to API: %s", payload)

    try: 
        response = requests.post("http://localhost:8000/book", json = payload)
        log.info("Appointment booked: %s", response.json())
        return response.json()
    except Exception as e:
        return {"status": "failed", "reason": str(e)}    
    

# ─── Tool 2: Self-care advice (RAG stub) ─────────────────────────────────────

def tool_self_care_advice(triage_summary: str, patient: dict, follow_up_answer: list) -> dict:
    """
    Generates self-care advice.
    Currently: direct LLM call.
    FUTURE: replace with MedRAG toolkit — retrieve relevant medical guidelines
            from vector DB, then pass retrieved context + summary to LLM.
    """
    log.info("TOOL CALL: self_care_advice | summary=%s", triage_summary[:80])

    # integrate follow-up answers into RAG context retrieval
    rag_query = f"{triage_summary} {' '.join(follow_up_answer)}"    
    rag_context = retrieve_dept_context(rag_query)

    chronic = ", ".join(patient.get("chronic_diseases", [])) or "none"
    meds    = ", ".join(patient.get("medications", []))      or "none"

    system = (
        "You are a medical assistant providing self-care advice. "
        "Given a triage summary and patient background, provide:\n"
        "1. Clear self-care steps the patient can take at home\n"
        "2. Warning signs that require immediate medical attention\n"
        "3. An estimate of when improvement should be expected\n"
        "Be concise, evidence-based, and considerate of the patient's existing conditions."
    )

    user = (
        f"Triage summary: {triage_summary}\n"
        f"Patient chronic diseases: {chronic}\n"
        f"Current medications: {meds}\n\n"
        f"Medical guideline context: {rag_context}\n\n"
        f"Follow-up answers: {' '.join(follow_up_answer)}\n\n"
        "Please provide self-care advice."
    )

    advice_text = call_llm(system, user)
    log.info("Advice generated (first 120 chars): %s", advice_text[:120])

    return {
        "advice":        advice_text,
        "generated_at":  datetime.utcnow().isoformat(),
    }

# ─── Prompts ──────────────────────────────────────────────────────────────────

QUESTION_SYSTEM = """
You are a medical triage agent.

At each step, decide whether:
1. You need MORE information → ask ONE follow-up question
2. You have ENOUGH information → make a decision

You must respond with JSON:

If asking:
{"action": "ask_question", "question": "<text>", "reasoning": "<why>"}

If deciding:
{"action": "make_decision", "symptom_category": "<short phrase>", "reasoning": "<why>"}

Rules:
- Ask only ONE question at a time
- Do NOT repeat questions
- Stop asking when confident
- Be safe: if unsure → ask more
- You MUST base every reasoning and decision **only** on symptoms and information that have been explicitly stated in the initial triage summary or the patient's answers. 
- Never assume, invent, or mention any information (duration, severity, progression, associated symptoms, etc.) that the patient has not explicitly stated.
"""

DECISION_SYSTEM = """You are a clinical triage assistant making a medical decision.
Based on the triage summary, patient answers and medical guidelines, decide whether the patient needs
a medical appointment or can manage with self-care at home.

Consider:
- Red flags (chest pain, severe symptoms, rapid progression) → appointment
- Mild, stable, short-duration symptoms in otherwise healthy patients → self_care
- Chronic disease patients with relevant flare-ups → appointment

Respond with ONLY a valid JSON object and nothing else:
{"decision": "appointment" | "self_care", "symptom_category": "<short phrase>", "reasoning": "<one sentence>"}"""


REFLECTION_SYSTEM = """
You are a senior medical reviewer.

Review the previous decision for safety and correctness.

Check:
- Did we miss any red flags?
- Is the decision too risky?
- Is more caution needed?

Respond ONLY in JSON:

If the decision is OK:
{"status": "approve"}

If NOT:
{"status": "revise", "reason": "<why>", "suggested_decision": "appointment" | "self_care"}
"""

# ─── Phase 1: Follow-up questioning loop ─────────────────────────────────────

def run_followup_loop(triage_input: dict, patient_id: str) -> dict:
    """
    Runs a dynamic follow-up loop inspired by the MediQ approach. After every response,
    the agent evaluates whether more questions are needed or not.
    """
    log.info("=== Agent 3 START | patient=%s ===", patient_id)
    log.info("Triage input: %s", triage_input)

    patient        = load_patient(patient_id)
    triage_summary = triage_input.get("summary", "")
    history: list[dict] = []
    answers: list[str]  = []

    turn = 0

    # ── Questioning phase (maximal 4 turns) ──────────────────────────────────────────
    while turn < 5:
        # Build history text for the prompt
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
            log.warning("Bad JSON — forcing stop")
            break

        if data["action"] == "make_decision":
            log.info("Model decided to stop questioning")
            break
        
        question = data["question"]
        history.append({"role": "assistant", "content": question})
        log.info(f"Q{turn + 1}:{question}")

        print(f"\nAgent: {question}")
        answer = input("Patient: ").strip()

        log.info(f"A{turn + 1}: {answer}")
        answers.append(answer)
        history.append({"role": "user", "content": answer})

        turn += 1


    return {
        "patient": patient,
        "answers": answers,
        "history": history,
        "triage_summary": triage_summary,
    }
        
def make_decision(context: dict) -> dict:

    triage_summary = context["triage_summary"]
    answers = context["answers"]

    answers_text = "\n".join(answers)
    
    # RAG uses summary from first agent and patient context
    rag_query = f"{triage_summary} {answers_text}"
    rag_context = retrieve_dept_context(rag_query)

    # include triage summary, patient answers, and DEPT guidlines in promt (query for llm)
    decision_prompt = (
        f"Triage summary: {triage_summary}\n"
        f"Medical guideline context: {rag_context}\n\n"
        f"Follow-up answers:\n{answers_text}\n\n"
        "Make your decision now."
    )

    log.info("Calling decision LLM...")
    decision_raw = call_llm(DECISION_SYSTEM, decision_prompt)
    log.info("Decision raw response: %s", decision_raw)

    try:
        decision = json.loads(decision_raw)
    except:
        decision = {"decision": "appointment", "reasoning": "fallback"}

    # reflection loop

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
    except:
        log.warning("Reflection failed — keeping original decision")
        return decision
    
    if reflection.get("status") == "approve":
        log.info("Reflection approved the decision")
        return decision
    
    elif reflection["status"] == "revise":
        log.info("Decision revised due to reflection: %s", reflection["reason"])

        return {
            "decision": reflection["suggested_decision"],
            "symptom_category": decision.get("symptom_category", "general"),
            "reasoning": f"Revised: {reflection['reason']}"
        }


    log.info("Decision: %s", decision)
    return decision


# ─── Phase 2: Confirmation + action ──────────────────────────────────────────

def get_confirmation():
    MAX_RETRIES = 3

    for attempt in range(MAX_RETRIES):

        confirmation = input("Patient: ").strip().lower()
        if confirmation in ("yes", "y", "yeah", "yep", "sure", "ok", "okay", "ja", "j"):
            return True

        elif confirmation in ("no", "n", "nope", "nah", "nej"):
            return False

        else:
            print("\nAgent: I didn’t quite understand. Please answer with 'yes' or 'no'.")
    
    # fallback after multiple invalid attempts
    print("\nAgent: I will assume you do NOT want to book an appointment.")
    return False

def run_agent(triage_input: dict, patient_id: str) -> dict:
    """
    Full agent pipeline:
      1. dynamic Follow-up questioning loop
      2. Decision with reflections
      3. If appointment → confirm with patient → book or fall back to advice
      4. If self_care   → generate advice directly
    FUTURE: expose as FastAPI endpoint or subscribe to a queue topic.
    """
    # Step 1: ask follow up questions
    context         = run_followup_loop(triage_input, patient_id)
    follow_up_answers = context["answers"]
    patient        = context["patient"]
    history     = context["history"]

    qa_pairs = []

    for i in range(0, len(history), 2):
        if i + 1 < len(history):
            qa_pairs.append({
                "question": history[i]["content"],
                "answer": history[i + 1]["content"]
            })

    
    # Step 2: decide appointment or self-care advice
    decision_ojb = make_decision(context)
    
    decision = decision_ojb.get("decision", "appointment")
    category = decision_ojb.get("symptom_category", "general")
    reasoning = decision_ojb.get("reasoning", "No reasoning provided.")


    log.info("Final decision: %s | category: %s | reasoning: %s", decision, category, reasoning)
    
    
    # Step 3: call functions based on decision
    if decision == "appointment":
        # ── Confirm with patient before booking ──────────────────────────────
        print(
            f"\nAgent: Based on your answers, I recommend booking a medical appointment "
            f"({reasoning}). Would you like me to book an appointment for you? (yes/no)"
        )

        confirmed = get_confirmation()
        
        #if confirmation in ("yes", "y", "yeah", "yep", "sure", "ok", "okay", "ja", "j"):
        if confirmed:
            tool_result = tool_book_appointment(category, patient_id)
            
            print ("Your appointment has been booked: ", tool_result)
            output = {
                "action":     "appointment",
                "booking":    tool_result,
                "patient_id": patient_id,
                "answers":    qa_pairs,
                "reasoning":  reasoning,
            }
        else:
            # Patient declined — fall back to self-care advice
            log.info("Patient declined appointment — generating self-care advice instead")
            print("\nAgent: Understood. Let me give you some self-care advice instead.")
            tool_result = tool_self_care_advice(triage_input.get("summary", ""), patient, follow_up_answers)
            print(f"\nAgent: {tool_result['advice']}")
            output = {
                "action":     "self_care_after_declined_appointment",
                "advice":     tool_result,
                "patient_id": patient_id,
                "answers":    qa_pairs,
                "reasoning":  reasoning,
            }
            

    else:
        # ── Self-care advice ──────────────────────────────────────────────────
        tool_result = tool_self_care_advice(triage_input.get("summary", ""), patient, follow_up_answers)
        print(f"\nAgent: {tool_result['advice']}")
        output = {
            "action":     "self_care",
            "advice":     tool_result,
            "patient_id": patient_id,
            "answers":    qa_pairs,
            "reasoning":  reasoning,
        }

    log.info("Agent output: %s", json.dumps(output, indent=2))

    # FUTURE: publish output to next agent / orchestrator via message queue
    return output

# ─── CLI entry ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Simulated triage agent output — replace with real inter-agent message
    # FUTURE: receive via message queue / REST call from Agent 1 or Agent 2
    sample_triage = {
        "summary": "Patient is a 45-year-old male reporting recurring chest tightness and shortness of breath.",
        "urgency": "medium",
    }
    print("=== Starting Agent 3: Medical Follow-Up & Decision Agent ===")

    final = run_agent(triage_input=sample_triage, patient_id="P001")
    print("\n=== Agent 3 Final Output ===")
    print(json.dumps(final, indent=2))
