from typing import Optional, List
from deepteam.test_case import RTTurn, ToolCall
import asyncio
import json

# Import your agents
from agent1_noninteractive import main as agent1_main  
from agent2 import run_routing_agent as agent2_main
from agent3_noninteractive import run_agent3_non_interactive as agent3_main


async def agent1_callback(input: str) -> str:
    try:
        result = agent1_main(symptoms=input, subject_id="P003", postal_code="2200")
        full_response = f"""
        Tiage Response: {result.get('triage_response')}
        Routing Desicion: {result.get('routing')}
        """

        return RTTurn(
            role="assistant",
            content=full_response,
            retrieval_context=[],
            tools_called=[]  # Agent 1 doesn't call external tools
        )

    except Exception as e:
        return RTTurn(
            role="assistant",
            content=f"Agent 1 Error: {str(e)}"
        )
        

async def agent2_callback(input: str) -> str:
    try:
        emergency_data = {
            "patient_id": "P003",
            "symptoms": input,
            "score": 1,                    # Force high urgency for testing
            "location": "2200"
        }
        result = agent2_main(emergency_data, max_steps=3)

        # Convert result to clean string
        if isinstance(result, dict):
            content = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            content = str(result)

        tools = []
        if "hospital" in content.lower() or "ambulance" in content.lower():
            tools.append(ToolCall(
                name="hospital_lookup",
                args={"department": "Emergency", "location": "2400"},
                result="Hospital info returned"
            ))

        return RTTurn(
            role="assistant",
            content=content,
            retrieval_context=[],
            tools_called=tools
        )
    except Exception as e:
        return RTTurn(role="assistant", content=f"Agent 2 Error: {str(e)}")
    

async def agent3_callback(input: str, turns: Optional[List[RTTurn]] = None) -> RTTurn:
    """
    DeepTeam-compatible callback for Agent 3.
    Supports CrescendoJailbreaking and other multi-turn attacks.
    """
    try:
        # Optional: You can reconstruct conversation history from 'turns' if needed
        conversation_history = []
        if turns:
            for turn in turns:
                conversation_history.append({
                    "role": turn.role,
                    "content": turn.content
                })

        # Run your Agent 3 logic (non-interactive but multi-turn capable)
        result = agent3_main(
            symptoms=input,
            patient_id="TEST_PATIENT_001"
            # You could pass simulated_answers based on history if you want more control
        )

        # Extract key info for better attack evaluation
        decision = result.get("decision", "unknown")
        reasoning = result.get("reasoning", "")

        content = f"""
{result['final_message']}

Decision: {decision.upper()}
Reasoning: {reasoning}
"""

        # Optional: Track tool usage for ExploitToolAgent etc.
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
            retrieval_context=["DEPT guidelines + patient history from ChromaDB"],
            tools_called=tools_called
        )

    except Exception as e:
        return RTTurn(
            role="assistant",
            content=f"Agent 3 encountered an error: {str(e)}",
            retrieval_context=[]
        )