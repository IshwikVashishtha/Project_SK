import logging
from agentstate import AgentState, UserState, ConversationState, TaskState, MemoryState, ToolState, EnvironmentState, PlanningState, LearningState, SafetyState

logging.basicConfig(level=logging.INFO)


logger  = logging.getLogger(name= "Input_node")


async def __input_node__(state: AgentState) -> dict:
    """
    Input node to initialize the agent state.
    """
    # Extract user_input safely
    if hasattr(state, "user_input"):
        user_input = state.user_input
    elif isinstance(state, dict):
        user_input = state.get("user_input", "")
    else:
        user_input = ""

    if not user_input:
        raise ValueError('Input is Empty. Give me work to do.')
        
    logger.info(f"User input: {user_input}")
    initial_state = {
        "user_input": user_input,
        "conversation_state": ConversationState(),
        "task_state": TaskState(),
        "memory_state": MemoryState(),
        "tool_state": ToolState(),
        "environment_state": EnvironmentState(),
        "planning_state": PlanningState(),
        "learning_state": LearningState(),
        "safety_state": SafetyState(),
        "next": list[str]
    }
    
    # Returning the dictionary of state updates
    return initial_state
