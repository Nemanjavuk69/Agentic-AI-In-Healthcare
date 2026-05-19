from typing import Optional, List
from deepteam.test_case import RTTurn, ToolCall
import json

from agent1_noninteractive import main as agent1_main
from agent3_noninteractive import run_agent3_non_interactive as agent3_main

# Patient P-5AA379 = Kevin Carlsen (old P003)
# Has: Cancer, Antiretrovirals, Nuts + Penicillin allergies
# Richest medical profile — gives leak detector the best chance of catching disclosures
TEST_PATIENT_ID = "P-5AA379"


async def agent1_callback(input: str) -> RTTurn:
    try:
        result = agent1_main(
            symptoms=input,
            subject_id=TEST_PATIENT_ID,
            postal_code="2200"
        )
        content = (
            f"Triage Response: {result.get('triage_response')}\n"
            f"Routing Decision: {result.get('routing')}"
        )
        return RTTurn(
            role="assistant",
            content=content,
            retrieval_context=[],
            tools_called=[]
        )
    except Exception as e:
        return RTTurn(
            role="assistant",
            content=f"Agent 1 Error: {str(e)}"
        )


async def agent3_callback(input: str, turns: Optional[List[RTTurn]] = None) -> RTTurn:
    """
    DeepTeam-compatible callback for Agent 3.
    Supports CrescendoJailbreaking and other multi-turn attacks.
    """
    try:
        result = agent3_main(
            symptoms=input,
            patient_id=TEST_PATIENT_ID
        )

        decision  = result.get("decision", "unknown")
        reasoning = result.get("reasoning", "")
        content   = (
            f"{result['final_message']}\n\n"
            f"Decision: {decision.upper()}\n"
            f"Reasoning: {reasoning}"
        )

        tools_called = []
        if "appointment" in decision.lower():
            tools_called.append(ToolCall(
                name="book_appointment",
                args={"specialty": result.get("category", "general")},
                result="Appointment booked"
            ))
        else:
            tools_called.append(ToolCall(
                name="self_care_advice",
                args={},
                result="Advice generated"
            ))

        return RTTurn(
            role="assistant",
            content=content.strip(),
            retrieval_context=["DEPT guidelines retrieved from ChromaDB"],
            tools_called=tools_called
        )
    except Exception as e:
        return RTTurn(
            role="assistant",
            content=f"Agent 3 Error: {str(e)}",
            retrieval_context=[]
        )