"""
interfaces/cli.py

Command-Line Interface for DeepAgent.
Run directly: python interfaces/cli.py
"""

from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import Orchestrator
BIGBANNER = r"""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║                   ██╗███████╗██╗  ██╗ ██████╗                      ║
║                   ██║██╔════╝██║  ██║██╔═══██╗                     ║
║                   ██║███████╗███████║██║   ██║                     ║
║                   ██║╚════██║██╔══██║██║▄▄ ██║                     ║
║                   ██║███████║██║  ██║╚██████╔╝                     ║
║                   ╚═╝╚══════╝╚═╝  ╚═╝ ╚══▀▀═╝                      ║
║                                                                    ║
║                         S K I S H Q                                ║
║              Multi-Agent AI Assistant • SK Engine v2.0             ║
║                                                                    ║
╠════════════════════════════════════════════════════════════════════╣
║  Type your message and press Enter                                 ║
║                                                                    ║
║  Commands:                                                         ║
║    /status    Show agent status                                    ║
║    /clear     Clear memory                                         ║
║    /help      Show help                                            ║
║    /exit      Quit                                                 ║
╚════════════════════════════════════════════════════════════════════╝
"""
# BIGBANNER = r"""
#                                 ╔════════════════════════════════════════════════════════════════════════════╗
#                                 ║                                                                            ║
#                                 ║  ███████╗██╗  ██╗    ███╗   ███╗██╗    █████╗ ███╗   ███╗ ██████╗ ██████╗  ║
#                                 ║  ██╔════╝██║ ██╔╝    ████╗ ████║██║   ██╔══██╗████╗ ████║██╔═══██╗██╔══██╗ ║
#                                 ║  ███████╗█████╔╝     ██╔████╔██║██║   ███████║██╔████╔██║██║   ██║██████╔╝ ║
#                                 ║  ╚════██║██╔═██╗     ██║╚██╔╝██║██║   ██╔══██║██║╚██╔╝██║██║   ██║██╔══██╗ ║
#                                 ║  ███████║██║  ██╗    ██║ ╚═╝ ██║██║   ██║  ██║██║ ╚═╝ ██║╚██████╔╝██║  ██║ ║
#                                 ║  ╚══════╝╚═╝  ╚═╝    ╚═╝     ╚═╝╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ║
#                                 ║                                                                            ║
#                                 ║               SK MI AMOR • Multi-Agent AI Assistant                        ║
#                                 ║                         SK Engine v2.0                                     ║
#                                 ║                                                                            ║
#                                 ╠════════════════════════════════════════════════════════════════════════════╣
#                                 ║  Type your message and press Enter                                         ║
#                                 ║                                                                            ║
#                                 ║  Commands:                                                                 ║
#                                 ║    /status    Show agent status                                            ║
#                                 ║    /clear     Clear memory                                                 ║
#                                 ║    /help      Show help                                                    ║
#                                 ║    /exit      Quit                                                         ║
#                                 ╚════════════════════════════════════════════════════════════════════════════╝
# """
HELP_TEXT = """
Available commands:
  /status   – Show sub-agent status
  /clear    – Clear conversation memory
  /help     – Show this help
  /exit     – Quit

Capabilities:
  • Research  – web search, Wikipedia lookups
  • Media     – play/pause/skip YouTube (say "play <song name>")
  • Data      – maths, unit conversion, CSV analysis
  • System    – weather, date/time, system info
  • Chat      – general conversation and follow-ups
"""


def run_cli():
    # print("\033[95m" + BIGBANNER + "\033[0m") #megenta
    print("\033[94m" + BIGBANNER + "\033[0m")

    try:
        agent = Orchestrator()
    except Exception as e:
        print(f"Failed to initialise Orchestrator: {e}")
        sys.exit(1)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # Built-in commands
        if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
            print("Goodbye!")
            break
        elif user_input.lower() == "/status":
            print(agent.get_status())
            continue
        elif user_input.lower() == "/clear":
            agent.clear_memory()
            print("Memory cleared.")
            continue
        elif user_input.lower() == "/help":
            print(HELP_TEXT)
            continue

        # Process
        print("\nSK: ", end="", flush=True)
        response = agent.invoke(user_input)
        print(response[0]["text"])


if __name__ == "__main__":
    run_cli()