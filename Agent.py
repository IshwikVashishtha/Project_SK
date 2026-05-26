from langgraph.graph import StateGraph , START , END
from agentstate import AgentState
from Agent_nodes.Input_node import __input_node__ as input_node
from Agent_nodes.Planning_node import planner_node
from Agent_nodes.file_node import file_node
from Agent_nodes.browser_node import browser_node
from Agent_nodes.research_node import research_node
from Agent_nodes.conversation_node import conversation_node
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def route_after_planner(state: AgentState):
    """
    Routes from planner to the first agent in the plan.
    """
    next_action = state.get("planning_state", {}).get("next_action", "done")
    if next_action == "research": return "research"
    if next_action == "file": return "file"
    if next_action == "browser": return "browser"
    if next_action == "conversation": return "conversation"
    return "end"

def route_after_agent(state: AgentState):
    """
    Routes back to the next agent in the plan or to the end.
    """
    next_action = state.get("planning_state", {}).get("next_action", "done")
    if next_action == "research": return "research"
    if next_action == "file": return "file"
    if next_action == "browser": return "browser"
    if next_action == "conversation": return "conversation"
    return "end"

def build_graph():

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("input" , input_node)
    graph.add_node("planner", planner_node)
    graph.add_node("file_node", file_node)
    graph.add_node("browser_node", browser_node)
    graph.add_node("research_node", research_node)
    graph.add_node("conversation_node", conversation_node)

    # Entry point
    graph.add_edge(START ,"planner")
    # graph.add_edge("input", "planner")
    
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "research": "research_node",
            "file": "file_node",
            "browser": "browser_node",
            "conversation": "conversation_node",
            "end": END
        }
    )

    # Add routing after each worker node back to the plan
    for node_name in ["research_node", "file_node", "browser_node", "conversation_node"]:
        graph.add_conditional_edges(
            node_name,
            route_after_agent,
            {
                "research": "research_node",
                "file": "file_node",
                "browser": "browser_node",
                "conversation": "conversation_node",
                "end": END
            }
        )

    graph_pic = graph.compile()
    # print(graph_pic.get_graph().draw_mermaid())
    return graph_pic

# Note: To use the graph, call build_graph() to get a compiled graph instance.
# Example: graph = build_graph()
async def run_agent(user_input: str):
    """
    Entry point for running the LangGraph agent.
    """

    logger.info("Starting Agent Graph from user query")

    graph = build_graph()

    result = await graph.ainvoke({"user_input": user_input})

    logger.info("Agent finished execution")
    return result

