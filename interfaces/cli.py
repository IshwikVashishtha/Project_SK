from __future__ import annotations
import os, sys
import pathfinder
from Agent import build_graph
import logging
from agentstate import AgentState
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
from Agent import run_agent
BIGBANNER = """ 
██████╗ ██╗   ██╗███╗   ███╗██████╗ ██╗     ███████╗██████╗ ███████╗███████╗
██╔══██╗██║   ██║████╗ ████║██╔══██╗██║     ██╔════╝██╔══██╗██╔════╝██╔════╝
██████╔╝██║   ██║██╔████╔██║██████╔╝██║     █████╗  ██████╔╝█████╗  █████╗  
██╔══██╗██║   ██║██║╚██╔╝██║██╔══██╗██║     ██╔══╝  ██╔══██╗██╔══╝  ██╔══╝  
██████╔╝╚██████╔╝██║ ╚═╝ ██║██████╔╝███████╗███████╗██████╔╝███████╗███████╗
╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚═════╝ ╚══════╝╚══════╝╚═════╝ ╚══════╝╚══════╝  
╔═════════════════════════════════════╗          
║ DeepAgent • SK v2.0                 ║         
║ Multi-Agent AI Assistant (CLI Mode) ║          
╚═════════════════════════════════════╝         
Type your message and press Enter.         
Commands: /status /clear /help /exit              
"""
HELP = """
Commands:
  /status              – All agent + MCP server status
  /mcp                 – MCP server status only
  /reconnect           – Reconnect all MCP servers
  /reconnect <name>    – Reconnect one server  (e.g. /reconnect github)
  /clear               – Clear conversation memory
  /help                – This message
  /exit                – Quit

Agents:
  Research   – web search, Wikipedia
  Media      – YouTube play / pause / skip ad
  Data       – maths, unit conversion, CSV analysis
  System     – weather, date / time, OS info
  MCP        – files, git, GitHub, email, Slack, DB, browser, memory...
  Chat       – general conversation (fallback)
"""


def run_cli():
    print("\033[95m" + BIGBANNER + "\033[0m")

    try:
        logger.info("Starting Agent Graph from user query")
        graph = build_graph()  
    except Exception as e:
        print(f"Failed to start Agent Graph: {e}")
        sys.exit(1)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            initial_state = {
        "user_input": user_input
    }
            # result = graph.ainvoke(input=initial_state)
            logger.info("Agent finished execution")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        low = user_input.lower()

        if low in ("/exit", "/quit"):
            print("Goodbye!")
            break

        elif low == "/status":
            print(graph.get_status())

        elif low == "/mcp":
            print(graph.get_status())

        elif low.startswith("/reconnect"):
            parts = user_input.split()
            server = parts[1] if len(parts) > 1 else None
            print(graph.reconnect(server))

        elif low == "/clear":
            graph.clear_memory()
            print("Memory cleared.")

        elif low == "/help":
            print(HELP)

        else:
            print("\nSK: ", end="", flush=True)
            response = run_agent(user_input)
            print(response)


if __name__ == "__main__":
    run_cli()