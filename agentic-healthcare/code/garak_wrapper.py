from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import sys
import os

sys.path.append(os.path.dirname(__file__))

from utils import call_llm
from agent1 import triage_agent, is_symptom_input
from agent2 import run_agent as run_agent2
from agent3 import run_agent as run_agent3

app = FastAPI(title="Garak - Individual Agent Testers")

class PromptRequest(BaseModel):
    prompt: str
    subject_id: str = "GARAK_TEST_001"
    postal_code: str = "2200"


# ====================== AGENT 1 ======================
@app.post("/agent1")
async def test_agent1(request: PromptRequest):
    """Test only the Triage Agent (Agent 1)"""
    if not is_symptom_input(request.prompt):
        return {"agent": "1", "response": "I can only assist with medical symptoms."}

    visit_history = "No previous visits on record."
    result = triage_agent(request.prompt, visit_history)
    
    return {
        "agent": "1",
        "response": result.get("response", ""),
        "triage_score": result.get("score"),
        "status": "success"
    }


# ====================== AGENT 2 ======================
@app.post("/agent2")
async def test_agent2(request: PromptRequest):
    """Test Emergency Response Agent (Agent 2)"""
    emergency_data = {
        "patient_id": request.subject_id,
        "symptoms": request.prompt,
        "score": 1,                    # Force high urgency for testing
        "location": request.postal_code
    }
    result = run_agent2(emergency_data)
    
    return {
        "agent": "2",
        "response": str(result),
        "status": "success"
    }


# ====================== AGENT 3 ======================
@app.post("/agent3")
async def test_agent3(request: PromptRequest):
    """Test Medical Follow-up Agent (Agent 3) with fake inputs"""
    triage_input = {
        "summary": request.prompt,
        "urgency": "Triage level: 4 GRØN"
    }

    # Patch input() to make Agent 3 non-interactive
    original_input = __builtins__.input
    def fake_input(prompt=""):
        # Return safe, neutral answers
        if "pain" in prompt.lower() or "how long" in prompt.lower():
            return "Moderate pain for 3 days."
        elif "worse" in prompt.lower() or "better" in prompt.lower():
            return "It is stable."
        return "Yes."

    __builtins__.input = fake_input
    
    try:
        result = run_agent3(triage_input=triage_input, patient_id=request.subject_id)
    finally:
        __builtins__.input = original_input

    return {
        "agent": "3",
        "action": result.get("action", "unknown"),
        "response": str(result),
        "status": "success"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    print("🚀 Garak Multi-Agent Wrapper running on http://127.0.0.1:8001")
    print("Endpoints:")
    print("   → POST /agent1")
    print("   → POST /agent2")
    print("   → POST /agent3")
    uvicorn.run(app, host="127.0.0.1", port=8001)