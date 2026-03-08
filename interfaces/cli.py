from __future__ import annotations
import os, sys
import pathfinder

from agents.orchestrator import Orchestrator
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
        agent = Orchestrator()
    except Exception as e:
        print(f"Failed to start Orchestrator: {e}")
        sys.exit(1)

    while True:
        try:
            user_input = input("\nYou: ").strip()
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
            print(agent.get_status())

        elif low == "/mcp":
            print(agent.mcp_agent.get_status())

        elif low.startswith("/reconnect"):
            parts = user_input.split()
            server = parts[1] if len(parts) > 1 else None
            print(agent.mcp_agent.reconnect(server))

        elif low == "/clear":
            agent.clear_memory()
            print("Memory cleared.")

        elif low == "/help":
            print(HELP)

        else:
            print("\nSK: ", end="", flush=True)
            response = agent.invoke(user_input)
            print(response)


if __name__ == "__main__":
    run_cli()