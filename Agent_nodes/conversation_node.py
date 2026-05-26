import logging
from agentstate import AgentState
from agents.conversation_agent import ConversationAgent

logger = logging.getLogger("conversation_node")

async def conversation_node(state: AgentState) -> dict:
    """
    Node for handling general chat and conversation.
    """
    logger.info("--- CONVERSATION NODE ---")
    
    # Check if we are in a multi-step plan
    task_state = state.get("task_state", {})
    subtasks = task_state.get("subtasks", [])
    completed = task_state.get("completed_steps", [])
    
    current_task = None
    if subtasks:
        for i, task in enumerate(subtasks):
            if task["agent"] == "conversation" and task.get("status") != "completed":
                current_task = task
                task_index = i
                break
    
    if current_task:
        context = ""
        if completed:
            context = "\n\nPrevious results for context:\n" + "\n".join(completed)
        query = current_task["query"] + context
        logger.info(f"Executing subtask: {current_task['query']}")
    else:
        if hasattr(state, "user_input"):
            query = state.user_input
        elif isinstance(state, dict):
            query = state.get("user_input", "")
        else:
            query = ""

    if not query:
        return {"task_state": {"status": "failed", "error": "No input provided"}}

    # Initialize ConversationAgent
    agent = ConversationAgent()
    
    try:
        response = await agent.invoke(query)
        logger.info(f"ConversationAgent response: {response}")
        
        if current_task:
            subtasks[task_index]["status"] = "completed"
            subtasks[task_index]["result"] = response
            completed.append(f"ConversationAgent: {response}")
            
            next_agent = "done"
            for t in subtasks:
                if t.get("status") != "completed":
                    next_agent = t["agent"]
                    break
                    
            return {
                "task_state": {
                    **task_state,
                    "subtasks": subtasks,
                    "completed_steps": completed,
                    "last_response": response,
                    "status": "in_progress" if next_agent != "done" else "completed"
                },
                "planning_state": {
                    "next_action": next_agent
                }
            }

        return {
            "task_state": {"status": "completed", "last_response": response},
            "conversation_state": {"active_intent": "conversation"}
        }
    except Exception as e:
        logger.error(f"Error in conversation_node: {e}")
        return {"task_state": {"status": "failed", "error": str(e)}}
