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

def get_location_coords(location): 
    mapping = {
        "2800": (55.770, 12.500),  # Lyngby
        "2100": (55.700, 12.580),  # Copenhagen Ø
        "2200": (55.690, 12.550),  # Copenhagen N
        "2300": (55.670, 12.600),  # Copenhagen S
        "2400": (55.680, 12.620),  # Copenhagen NV
    }

    return mapping.get(location[:4], (55.680, 12.620))  # default to NV coords

# euclidean distance in km (approx, assuming 1 degree ~ 111 km)
def calculate_distance(coord1, coord2):
    return ((coord1[0] - coord2[0])**2 + (coord1[1] - coord2[1])**2) ** 0.5 * 111

# Dummy hospital lookup tool (return fixed entry for demonstration)
def hospital_lookup(department, location):
    
    user_coords = get_location_coords(location)

    database = [
        {
            "hospital": "Rigshospitalet",
            "department": "Cardiology",
            #"distance_km": 5.2,
            "coords": (55.695, 12.566),
            "address": "Blegdamsvej 9, Copenhagen"
        },
        {
            "hospital": "Herlev Hospital",
            "department": "Emergency",
            #"distance_km": 8.5,
            "coords": (55.723, 12.443),
            "address": "Herlev Ringvej 75, Herlev"
        },
        {
            "hospital": "Bispebjerg Hospital",
            "department": "Emergency",
            #"distance_km": 6.0,
            "coords": (55.706, 12.533),
            "address": "Copenhagen"
        }
    ]

    # filter by department
    matches = [
        h for h in database
        if h["department"].lower() == department.lower()
    ]

    if not matches:
        matches = database

    for h in matches:
        h["distance_km"] = round(calculate_distance(user_coords, h["coords"]), 2)
    

    return sorted(matches, key=lambda x: x["distance_km"])[0]

def ambulance_dispatch(patient_id, location, distance_km):
    # assume avg speed of 40 km/h in city traffic
    speed_kmh = 40

    eta_minutes = int((distance_km / speed_kmh) * 60)
    
    log.info(f"Dispatching ambulance for patient {patient_id} to location {location}")
    # Simulate dispatch logic here
    return {"status": "dispatched", "eta_minutes": eta_minutes, "message": "Ambulance is on the way. Please wait at your location."}

# ─── Tool Registry ─────────────────────────────────────────────────────────────

TOOLS = {
    "hospital_lookup": hospital_lookup,
    "ambulance_dispatch": ambulance_dispatch
}

# ─── Main Execution ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are an autonomous healthcare routing agent.
You receive triage output and must make operational decisions.

You must decide step-by-step what to do using tools.

Available tools:
1. hospital_lookup(department, location)
2. ambulance_dispatch(patient_id, location, distance_km)

Rules:
- Think step-by-step
- Use tools when needed
- Finish as soon as you have enough information

Respond ONLY in JSON:

{
  "thought": "short reasoning",
  "action": "tool_name OR final",
  "action_input": { ... }
}

When you finish, you MUST return:

{
  "thought": "...",
  "action": "final",
  "action_input": {
    "message": "...",
    "hospital": "...",
    "department": "...",
    "address": "...",
    "transport": "ambulance or self-transport"
  }
}

Rules:
- If you have not called hospital_lookup, you are NOT allowed to finish
- Do NOT call the same tool more than once unless absolutely necessary
- Include ONLY real values from tool outputs
- Be concise
"""

def run_routing_agent(input_data, max_steps=4):
    context = {
        "input_data": input_data,
        "history": []
    }

    used_tools = set()

    for step in range(max_steps):
        log.info("Step %d: Agent thinking...", step + 1)

        user_promt = json.dumps(context)
        response = call_llm(SYSTEM_PROMPT, user_promt)

        try:
            decision = json.loads(response)
        except Exception as e:
            log.error("JSON parsing failed: %s", e)
            return "Agent failed (invalid response)"

        action= decision.get("action")
        action_input = decision.get("action_input", {})


        log.info(f"Action: {action}")
        log.info(f"Input: {action_input}")

        # 🔹 Final answer
        if action == "final":
            return action_input
        
        used_tools.add(action)
        context["used_tools"] = list(used_tools)
        

        # 🔹 Tool execution
        tool_fn = TOOLS.get(action)

        if not tool_fn:
            return f"Unknown tool: {action}"

        try:
            result = tool_fn(**action_input)
        except Exception as e:
            result = {"error": str(e)}

        log.info(f"Observation: {result}")

        # 🔹 Append to history (short memory)
        context["history"].append({
            "thought": decision["thought"],
            "action": action,
            "result": result
        })

    return "Agent stopped (max steps reached)"

# ─── Wrapper for Final Output ───────────────────────────────────────────────

def run_agent(input_data):

    result = run_routing_agent(input_data)

    print("\n" + "═" * 85)
    print(" " * 28 + "EMERGENCY RESPONSE ACTIVATED")
    print("═" * 85)

    if isinstance(result, dict):
        return f"""
Message: {result.get("message", "")}

Hospital: {result.get("hospital", "")}
Department: {result.get("department", "")}
Address: {result.get("address", "")}
Transport: {result.get("transport", "")}
"""
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
        "location": "2800 Lyngby"
    }

    final = run_agent(sample_triage)
    print("\n=== Agent 2 Final Output ===")
    print(final)
