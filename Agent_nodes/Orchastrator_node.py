import logging
from agentstate import AgentState
from agents.orchestrator import Orchestrator

logger = logging.getLogger("orchastrator_node")

async def orchastrator_node(state: AgentState) -> dict:
    """
    Orchestrator node that classifies user intent and routes to the correct agent node.
    """
    logger.info("--- ORCHESTRATOR NODE ---")
    
    # Extract user_input safely
    if hasattr(state, "user_input"):
        user_input = state.user_input
    elif isinstance(state, dict):
        user_input = state.get("user_input", "")
    else:
        user_input = ""

    if not user_input:
        logger.warning("No user input found in state")
        return {"task_state": {"status": "failed", "error": "No user input"}}

    # Initialize Orchestrator (Lazy or singleton would be better, but for now)
    orchestrator = Orchestrator()
    
    try:
        # We only want to classify here, not invoke the whole agent
        # because the graph will handle the routing to individual nodes
        intent = await orchestrator._llm_classify(user_input)
        logger.info(f"Classified intent: {intent}")
        
        # Update state with the active intent
        return {
            "conversation_state": {
                "active_intent": intent
            },
            "next": [f"{intent}_node"] # Suggesting the next node name
        }
    except Exception as e:
        logger.error(f"Error in orchastrator_node: {e}")
        return {
            "task_state": {
                "status": "failed",
                "error": str(e)
            }
        }
