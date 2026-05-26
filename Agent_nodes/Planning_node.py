import json
import logging
from typing import List, Dict
from agentstate import AgentState
from universal_llm import UniversalLLM
from config.settings import AGENT_LLM_CONFIG
from langchain_core.messages import SystemMessage, HumanMessage
from utility.logging import log
logger = logging.getLogger("PLANNER")

PLANNER_SYSTEM_PROMPT = """You are the Lead Strategic Planner for SK.
Your job is to take a user request and break it down into a sequence of steps for specific agents.

Available Agents:
- research: For web search, news, facts, and Wikipedia.
- browser: For YouTube, playing media, navigating complex sites, and automation.
- file: For creating, reading, finding, zipping files and folders.
- conversation: For general chat and small talk.

Rules:
1. Break complex requests into clear, logical steps.
2. If a step depends on the output of a previous step, note that in the query.
3. Respond ONLY with a JSON array of objects. Each object must have:
   - "agent": The name of the agent to use.
   - "query": The specific instruction for that agent.

Example:
User: "Search for AI news and save it to a file named news.txt"
Response:
[
  {"agent": "research", "query": "Find the latest news about Artificial Intelligence from today."},
  {"agent": "file", "query": "Create a file named news.txt with the research results provided."}
]
"""

class structure_of_output:
    subtasks: List[Dict[str, str]] = []

async def planner_node(state: AgentState) -> dict:
    """
    Analyzes the user input and creates a step-by-step plan.
    """
    logger.info("--- PLANNING NODE ---")
    log(f"Planner input: {state['user_input']}")
    
    # Extract user_input safely
    if hasattr(state, "user_input"):
        user_input = state.user_input
    elif isinstance(state, dict):
        user_input = state.get("user_input", "")
    else:
        user_input = ""

    if not user_input:
        return {"task_state": {"status": "failed", "error": "No input for planner"}}

    # Initialize LLM
    cfg = AGENT_LLM_CONFIG.get("orchestrator")
    llm = UniversalLLM(**cfg).get_model()

    try:
        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=f"Request: {user_input}")
        ]
        response = await llm.ainvoke(messages)
        content = getattr(response, "content", str(response)).strip()
        
        # Strip markdown fences if present
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        plan = json.loads(content)
        logger.info(f"Generated plan: {plan}")
        log(f"Generated plan")

        # Update state with the new plan
        return {
            "task_state": {
                "objective": user_input,
                "subtasks": plan,
                "completed_steps": [],
                "status": "in_progress",
                "priority": 1
            },
            "planning_state": {
                "current_plan": plan,
                "next_action": plan[0]["agent"] if plan else "done"
            }
        }
    except Exception as e:
        logger.error(f"Planner error: {e}")
        return {
            "task_state": {
                "status": "failed",
                "error": f"Planning failed: {str(e)}"
            }
        }
