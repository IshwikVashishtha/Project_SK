import logging
from agentstate import AgentState
from agents.file_agent import FileAgent

logger = logging.getLogger("file_node")

async def file_node(state: AgentState) -> dict:
    """
    Node for handling file and folder operations.
    """
    logger.info("--- FILE NODE ---")
    
    # Check if we are in a multi-step plan
    task_state = state.get("task_state", {})
    subtasks = task_state.get("subtasks", [])
    completed = task_state.get("completed_steps", [])
    
    current_task = None
    if subtasks:
        # Find the first pending subtask for this agent
        for i, task in enumerate(subtasks):
            if task["agent"] == "file" and task.get("status") != "completed":
                current_task = task
                task_index = i
                break
    
    # If no specific subtask, use the main user_input
    if current_task:
        # Inject context from previous results if available
        context = ""
        if completed:
            context = "\n\nPrevious results for context:\n" + "\n".join(completed)
        query = current_task["query"] + context
        logger.info(f"Executing subtask: {current_task['query']}")
        log(f"Executing subtask:{current_task['agent']} === >>> {current_task['query']}")
        
    else:
        if hasattr(state, "user_input"):
            query = state.user_input
        elif isinstance(state, dict):
            query = state.get("user_input", "")
        else:
            query = ""

    if not query:
        return {"task_state": {"status": "failed", "error": "No input provided"}}

    # Initialize FileAgent
    agent = FileAgent()
    
    try:
        response = await agent.invoke(query)
        logger.info(f"FileAgent response: {response}")
        
        # If part of a plan, update the subtask status
        if current_task:
            subtasks[task_index]["status"] = "completed"
            subtasks[task_index]["result"] = response
            completed.append(f"FileAgent: {response}")
            
            # Decide if there are more tasks
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
            "conversation_state": {"active_intent": "file"}
        }
    except Exception as e:
        logger.error(f"Error in file_node: {e}")
        return {"task_state": {"status": "failed", "error": str(e)}}
