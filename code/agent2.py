# =========================================
# ROUTING AGENT (EMERGENCY CASE)
# =========================================
# Handles emergency cases after triage (no medical diagnosis).
#
# INPUT:
# - patient_id, symptoms, category, severity, location
#
# WORKFLOW:
# 1. LLM decides:
#    - hospital department
#    - transport (ambulance / self)
#    - patient message
#
# 2. Hospital Lookup Tool:
#    - returns hospital info (name, address, distance)
#
# 3. Ambulance Tool (if needed):
#    - simulates dispatch and adds ETA to message
#
# 4. Output:
#    - combines message + hospital + transport
#
# LOGGING:
# - all steps logged to "agent2.log"
#
# WHY AGENTIC APPROACH:
# - decision logic is not hardcoded, but learned by LLM
# - allows integration of tools (lookup tool, ambulance dispatch)
# =========================================

import json
import logging
import re
import os

from utils import call_llm
from secure_comm import receive_secure_message


os.environ["TQDM_DISABLE"] = "1"
logging.getLogger().setLevel(logging.WARNING)


# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("agent2.log"),
        #logging.StreamHandler(),
    ],
)
log = logging.getLogger("agent2")

# ─── Tools ────────────────────────────────────────────────────────────────────

POSTAL_CODE_COORDS = {
    "1050": (55.676, 12.568),  # København K
    "1360": (55.679, 12.571),  # København K
    "1450": (55.675, 12.560),  # København K
    "1560": (55.672, 12.556),  # København V
    "1630": (55.673, 12.540),  # København V
    "1700": (55.676, 12.541),  # København V
    "1800": (55.683, 12.552),  # Frederiksberg C
    "1900": (55.686, 12.548),  # Frederiksberg C
    "2000": (55.685, 12.489),  # Frederiksberg
    "2100": (55.700, 12.580),  # København Ø
    "2200": (55.690, 12.550),  # København N
    "2300": (55.665, 12.602),  # København S / Amager
    "2400": (55.700, 12.515),  # København NV
    "2450": (55.650, 12.530),  # København SV
    "2500": (55.650, 12.485),  # Valby
    "2600": (55.650, 12.397),  # Glostrup
    "2610": (55.662, 12.410),  # Rødovre
    "2650": (55.629, 12.473),  # Hvidovre
    "2700": (55.740, 12.450),  # Brønshøj
    "2720": (55.731, 12.473),  # Vanløse
    "2730": (55.723, 12.443),  # Herlev
    "2740": (55.755, 12.395),  # Skovlunde
    "2800": (55.770, 12.500),  # Lyngby
    "2820": (55.770, 12.520),  # Gentofte
    "2860": (55.760, 12.540),  # Søborg
    "2900": (55.752, 12.549),  # Hellerup
    "2920": (55.739, 12.586),  # Charlottenlund
    "3000": (56.036, 12.613),  # Helsingør
    "3400": (55.927, 12.300),  # Hillerød
}

def get_location_coords(location):
    if not location:
        return POSTAL_CODE_COORDS["2400"]  # default to København NV

    match = re.search(r"\b(\d{4})\b", str(location))
    if not match:
        return POSTAL_CODE_COORDS["2400"]  # default to København NV

    postal_code = match.group(1)
    return POSTAL_CODE_COORDS.get(postal_code, POSTAL_CODE_COORDS["2400"])

# euclidean distance in km (approx, assuming 1 degree ~ 111 km)
def calculate_distance(coord1, coord2):
    return ((coord1[0] - coord2[0])**2 + (coord1[1] - coord2[1])**2) ** 0.5 * 111

HOSPITAL_DATABASE = [
    {"hospital": "Rigshospitalet", "department": "Cardiology", "coords": (55.695, 12.566), "address": "Blegdamsvej 9, 2100 København Ø"},
    {"hospital": "Rigshospitalet", "department": "Neurology", "coords": (55.695, 12.566), "address": "Blegdamsvej 9, 2100 København Ø"},
    {"hospital": "Rigshospitalet", "department": "Emergency", "coords": (55.695, 12.566), "address": "Blegdamsvej 9, 2100 København Ø"},

    {"hospital": "Bispebjerg Hospital", "department": "Emergency", "coords": (55.706, 12.533), "address": "Bispebjerg Bakke 23, 2400 København NV"},
    {"hospital": "Bispebjerg Hospital", "department": "Neurology", "coords": (55.706, 12.533), "address": "Bispebjerg Bakke 23, 2400 København NV"},

    {"hospital": "Herlev Hospital", "department": "Emergency", "coords": (55.723, 12.443), "address": "Herlev Ringvej 75, 2730 Herlev"},
    {"hospital": "Herlev Hospital", "department": "Cardiology", "coords": (55.723, 12.443), "address": "Herlev Ringvej 75, 2730 Herlev"},
    {"hospital": "Herlev Hospital", "department": "Orthopedics", "coords": (55.723, 12.443), "address": "Herlev Ringvej 75, 2730 Herlev"},

    {"hospital": "Hvidovre Hospital", "department": "Emergency", "coords": (55.629, 12.473), "address": "Kettegård Allé 30, 2650 Hvidovre"},
    {"hospital": "Hvidovre Hospital", "department": "Orthopedics", "coords": (55.629, 12.473), "address": "Kettegård Allé 30, 2650 Hvidovre"},

    {"hospital": "Amager Hospital", "department": "Emergency", "coords": (55.650, 12.621), "address": "Italiensvej 1, 2300 København S"},

    {"hospital": "Gentofte Hospital", "department": "Cardiology", "coords": (55.752, 12.549), "address": "Gentofte Hospitalsvej 1, 2900 Hellerup"},

    {"hospital": "Glostrup Hospital", "department": "Neurology", "coords": (55.666, 12.397), "address": "Valdemar Hansens Vej 13, 2600 Glostrup"},

    {"hospital": "Nordsjællands Hospital", "department": "Emergency", "coords": (56.036, 12.613), "address": "Dyrehavevej 29, 3400 Hillerød"},
    {"hospital": "Nordsjællands Hospital", "department": "Cardiology", "coords": (56.036, 12.613), "address": "Dyrehavevej 29, 3400 Hillerød"},
]

# Dummy hospital lookup tool (return fixed entry for demonstration)
def hospital_lookup(department, location):
    log.info("Hospital lookup in progress")

    user_coords = get_location_coords(location)

    matches = [
        h.copy()
        for h in HOSPITAL_DATABASE
        if h["department"].lower() == str(department).lower()
    ]

    if not matches:
        matches = [h.copy() for h in HOSPITAL_DATABASE if h["department"] == "Emergency"]

    for h in matches:
        h["distance_km"] = round(calculate_distance(user_coords, h["coords"]), 2)

    best = sorted(matches, key=lambda x: x["distance_km"])[0]
    log.info("Hospital match found")
    return best

def ambulance_dispatch(patient_id, location, distance_km):
    # assume avg speed of 40 km/h in city traffic
    speed_kmh = 40

    eta_minutes = max(1, int((distance_km / speed_kmh) * 60))
    
    # log.info(f"Dispatching ambulance for patient {patient_id} to location {location}")
    log.info("Ambulance dispatch initiated")

    # Simulate dispatch logic here
    return {"status": "dispatched", "eta_minutes": eta_minutes, "message": "Ambulance is on the way. Please wait at your location."}

# ─── Tool Registry ─────────────────────────────────────────────────────────────

TOOLS = {
    "hospital_lookup": hospital_lookup,
    "ambulance_dispatch": ambulance_dispatch
}

ALLOWED_ACTIONS = {"hospital_lookup", "ambulance_dispatch", "final"}

# ─── Main Execution ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are an autonomous healthcare routing agent.
You receive triage output and must make operational decisions.

You must decide step-by-step what to do using tools.

Available actions:
- hospital_lookup
- ambulance_dispatch
- final

Important:
- The "action" field must contain ONLY one of these exact strings:
  "hospital_lookup", "ambulance_dispatch", or "final"
- Do NOT include parentheses in the action field
- Do NOT write action names like hospital_lookup(...) or ambulance_dispatch(...)
- Put parameters only inside "action_input"

Respond ONLY in JSON with this structure:
{
  "thought": "short reasoning",
  "action": "hospital_lookup | ambulance_dispatch | final",
  "action_input": { ... }
}

Rules:
- The first action MUST be hospital_lookup
- Do NOT call ambulance_dispatch before hospital_lookup
- If you have not called hospital_lookup, you are NOT allowed to finish
- Do NOT call the same tool more than once
- Include ONLY real values from tool outputs
- If triage score is 1, ambulance dispatch is mandatory
- If triage score is 2, self-transport is the default unless the patient is explicitly unable to move
- Be concise
"""

def build_safe_history(history):
    safe_history = []
    for item in history:
        entry = {
            "action": item.get("action"),
            "status": "ok" if "error" not in item.get("result", {}) else "error"
        }

        if item.get("action") == "hospital_lookup":
            result = item.get("result", {})
            entry["result_summary"] = {
                "hospital": result.get("hospital"),
                "department": result.get("department"),
                "distance_km": result.get("distance_km")
            }

        elif item.get("action") == "ambulance_dispatch":
            result = item.get("result", {})
            entry["result_summary"] = {
                "status": result.get("status"),
                "eta_minutes": result.get("eta_minutes")
            }

        safe_history.append(entry)

    return safe_history

def build_final_response(llm_message, trusted_state, input_data):
    hospital = trusted_state.get("hospital_lookup")
    ambulance = trusted_state.get("ambulance_dispatch")

    if not hospital:
        return {"error": "Cannot finalize without hospital lookup result"}

    forced_ambulance = must_dispatch_ambulance(input_data)
    transport = "ambulance" if (ambulance or forced_ambulance) else "self-transport"

    final_message = llm_message or "Please go to the selected hospital for urgent evaluation."

    if transport == "ambulance":
        if ambulance and ambulance.get("eta_minutes") is not None:
            final_message += f" Ambulance ETA is approximately {ambulance['eta_minutes']} minutes."
        else:
            final_message += " Ambulance dispatch has been initiated."

    return {
        "message": final_message,
        "hospital": hospital.get("hospital", ""),
        "department": hospital.get("department", ""),
        "address": hospital.get("address", ""),
        "transport": transport
    }

def normalize_action_name(action):
    if not isinstance(action, str):
        return action
    action = action.strip()
    if "(" in action:
        action = action.split("(", 1)[0].strip()
    return action

def symptoms_indicate_immobility(symptoms: str) -> bool:
    if not symptoms:
        return False

    text = symptoms.lower()
    indicators = [
        "unable to move",
        "cannot move",
        "can't move",
        "immobile",
        "collapsed",
        "cannot stand",
        "can't stand",
        "unable to walk",
        "cannot walk",
        "can't walk",
        "unconscious",
        "paralyzed",
    ]
    return any(phrase in text for phrase in indicators)


def must_dispatch_ambulance(input_data: dict) -> bool:
    score = input_data.get("score")
    symptoms = input_data.get("symptoms", "")

    if score == 1:
        return True

    if score == 2 and symptoms_indicate_immobility(symptoms):
        return True

    return False

def run_routing_agent(input_data, max_steps=4):
    context = {
        "input_data": input_data,
        "history": []
    }

    used_tools = set()
    trusted_state = {
        "hospital_lookup": None,
        "ambulance_dispatch": None
    }

    for step in range(max_steps):
        log.info("Step %d: Agent thinking...", step + 1)

        safe_input_data = {
            "symptoms": input_data.get("symptoms"),
            "score": input_data.get("score"),
            "category": input_data.get("category"),
            "severity": input_data.get("severity")
        }

        safe_context = {
            "input_data": safe_input_data,
            "history": build_safe_history(context["history"]),
            "used_tools": list(used_tools)
        }

        user_prompt = json.dumps(safe_context)
        response = call_llm(SYSTEM_PROMPT, user_prompt)

        try:
            decision = json.loads(response)
        except Exception as e:
            log.error("JSON parsing failed: %s", e)
            return "Agent failed (invalid response)"

        action = normalize_action_name(decision.get("action"))
        action_input = decision.get("action_input", {})
        thought = decision.get("thought", "")

        log.info("Action: %s", action)
        log.info("Action input received")

        if action not in ALLOWED_ACTIONS:
            return f"Agent failed (invalid action): {action}"

        if trusted_state["hospital_lookup"] is None and action != "hospital_lookup":
            log.info("Overriding action to hospital_lookup because it must run first")
            action = "hospital_lookup"
            action_input = {
                "department": action_input.get("department", "Emergency"),
                "location": input_data.get("location")
            }

        if must_dispatch_ambulance(input_data):
            if trusted_state["hospital_lookup"] is not None and trusted_state["ambulance_dispatch"] is None:
                log.info("Overriding action to ambulance_dispatch due to enforced transport policy")
                action = "ambulance_dispatch"

        if action == "final":
            if trusted_state["hospital_lookup"] is None:
                return "Agent failed (attempted final without hospital_lookup)"

            llm_message = action_input.get("message", "")
            return build_final_response(llm_message, trusted_state, input_data)

        if action in used_tools:
            if action == "hospital_lookup" and trusted_state["hospital_lookup"] is not None:
                log.info("hospital_lookup already completed; forcing final decision instead")
                return build_final_response(
                    action_input.get(
                        "message",
                        "Please go to the selected hospital for urgent evaluation."
                    ),
                    trusted_state,
                    input_data
                )
            else:
                return f"Agent failed (repeated tool call not allowed): {action}"

        tool_fn = TOOLS.get(action)
        if not tool_fn:
            return f"Agent failed (unknown tool after normalization): {action}"

        used_tools.add(action)

        if action == "hospital_lookup":
            action_input = {
                "department": action_input.get("department", "Emergency"),
                "location": input_data.get("location")
            }

        elif action == "ambulance_dispatch":
            hospital_result = trusted_state["hospital_lookup"]
            if hospital_result is None:
                return "Agent failed (ambulance_dispatch before hospital_lookup)"

            action_input = {
                "patient_id": input_data.get("patient_id"),
                "location": input_data.get("location"),
                "distance_km": hospital_result.get("distance_km")
            }

        try:
            result = tool_fn(**action_input)
        except Exception as e:
            result = {"error": str(e)}

        # log.info("Observation: %s", result)
        log.info("Agent 2 completed")

        if "error" not in result:
            trusted_state[action] = result

        context["history"].append({
            "thought": thought,
            "action": action,
            "result": result
        })

    return "Agent stopped (max steps reached)"


# ─── Wrapper for Final Output ───────────────────────────────────────────────

def run_agent(input_data):

    #decrypt data and verify signature
    data = receive_secure_message(
        expected_receiver="agent2",
        encrypted_message=input_data
    )


    # log.info(f" Starting Agent 2 with input: {data}")
    log.info("Starting Agent 2 with secure message received")

    result = run_routing_agent(data)

    print("\n" + "─" * 85)
    print(" " * 28 + "EMERGENCY RESPONSE ACTIVATED")
    print("\n" + "─" * 85)

    return result


# ---- CLI for testing ----
if __name__ == "__main__":
    # Simulated triage agent output — replace with real inter-agent message
    # FUTURE: receive via message queue / REST call from Agent 1 or Agent 2
    sample_triage = {
        "patient_id": "P001",
        "symptoms": "Severe chest pain",
        "category": "cardiac",
        "severity": "high",
        "score": 1,
        "location": "2800 Lyngby"
    }

    final = run_agent(sample_triage)
    print("\n=== Agent 2 Final Output ===")
    print(final)
