"""
Telegram Bot Interface for DeepAgent.
Each user gets their OWN Orchestrator instance with isolated memory.

Install dependency: pip install python-telegram-bot

Run: python interfaces/telegram_bot.py
"""

from __future__ import annotations
import os, sys, logging
import pathfinder

import logging
from config.settings import TELEGRAM_BOT_TOKEN
from utility.file_handler import is_file_response, extract_path
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
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
# BIGBANNER = """ 
#     ███████╗██╗  ██╗    ███╗   ███╗██╗    █████╗ ███╗   ███╗ ██████╗ ██████╗  
#     ██╔════╝██║ ██╔╝    ████╗ ████║██║   ██╔══██╗████╗ ████║██╔═══██╗██╔══██╗ 
#     ███████╗█████╔╝     ██╔████╔██║██║   ███████║██╔████╔██║██║   ██║██████╔╝ 
#     ╚════██║██╔═██╗     ██║╚██╔╝██║██║   ██╔══██║██║╚██╔╝██║██║   ██║██╔══██╗ 
#     ███████║██║  ██╗    ██║ ╚═╝ ██║██║   ██║  ██║██║ ╚═╝ ██║╚██████╔╝██║  ██║ 
#     ╚══════╝╚═╝  ╚═╝    ╚═╝     ╚═╝╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝ 
                                                                                
#     ███████╗██╗  ██╗ ██████╗     ██████╗  ╔═════════════════════════════════════╗          
#     ██╔════╝██║ ██╔╝ ╚════██╗   ██╔═████╗ ║ DeepAgent • SK v2.0                 ║         
#     ███████╗█████╔╝   █████╔╝   ██║██╔██║ ║ Multi-Agent AI Assistant (CLI Mode) ║          
#     ╚════██║██╔═██╗  ██╔═══╝    ████╔╝██║ ╚═════════════════════════════════════╝         
#     ███████║██║  ██╗ ███████╗██╗╚██████╔╝ Type your message and press Enter.         
#     ╚══════╝╚═╝  ╚═╝ ╚══════╝╚═╝ ╚═════╝  Commands: /status /clear /help /exit              
#     """

def run_telegram_bot():
    print("\033[93m" + BIGBANNER + "\033[0m")
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not set in .env — Telegram interface disabled.")
        return

    try:
        from telegram import Update
        from telegram.ext import (
            ApplicationBuilder, CommandHandler,
            MessageHandler, filters, ContextTypes
        )
    except ImportError:
        print("python-telegram-bot not installed. Run: pip install python-telegram-bot")
        return

    from agents.orchestrator import Orchestrator

    # Per-user orchestrator instances (isolated memory per user)
    user_agents: dict[int, Orchestrator] = {}

    def get_agent(user_id: int) -> Orchestrator:
        if user_id not in user_agents:
            logger.info(f"New session for user {user_id}")
            user_agents[user_id] = Orchestrator()
        return user_agents[user_id]

    # ── Helpers ───────────────────────────────────────────────────

    async def send_response(update: Update, response: str):
        """
        Send text OR a file depending on what the agent returned.
        If the response starts with __FILE__:/path, send the file as a document.
        Otherwise send as a normal text message.
        """
        if is_file_response(response):
            file_path = extract_path(response)

            if not os.path.exists(file_path):
                await update.message.reply_text(
                    f"I tried to send you '{os.path.basename(file_path)}' "
                    f"but the file wasn't found at: {file_path}"
                )
                return

            try:
                with open(file_path, "rb") as f:
                    await update.message.reply_document(
                        document=f,
                        filename=os.path.basename(file_path),
                        caption=f"Here's your file: {os.path.basename(file_path)}",
                    )
                logger.info(f"Sent file: {file_path}")
            except Exception as e:
                await update.message.reply_text(
                    f"I found the file but couldn't send it: {e}"
                )
        else:
            # Normal text — split if too long (Telegram limit: 4096 chars)
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)

    # ── Command handlers ──────────────────────────────────────────

    async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 Hi! I'm SK, your AI assistant.\n\n"
            "I can help you with:\n"
            "  🔍 Research & web search\n"
            "  🎵 YouTube playback\n"
            "  🔢 Maths & data analysis\n"
            "  🌤 Weather & time\n"
            "  📁 Files — ask me to send, create, or find any file\n"
            "  🔧 MCP integrations (git, email, Slack, DB...)\n"
            "  💬 General conversation\n\n"
            "Just type anything — or ask me to send you a file!"
        )

    async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Commands:\n"
            "  /start   – Welcome message\n"
            "  /clear   – Clear your conversation memory\n"
            "  /status  – Show agent status\n"
            "  /mcp     – Show MCP server status\n"
            "  /help    – This message\n\n"
            "File examples:\n"
            '  "Send me a file named report.csv"\n'
            '  "Create a JSON file with the top 5 planets"\n'
            '  "Give me a Python script that prints hello world"\n'
            '  "Send me the README from my GitHub repo"\n'
        )

    async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Clear conversation memory for the current user."""
        uid = update.effective_user.id
        if uid in user_agents:
            await user_agents[uid].clear_memory()
        await update.message.reply_text("Memory cleared! Fresh start.")

    async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Show current status of all agents and MCP servers."""
        uid   = update.effective_user.id
        agent = get_agent(uid)
        await update.message.reply_text(agent.get_status())

    async def cmd_mcp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Show status of MCP servers only."""
        uid   = update.effective_user.id
        agent = get_agent(uid)
        await update.message.reply_text(agent.mcp_agent.get_status())

    # ── Message handler ───────────────────────────────────────────

    async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages by routing through the orchestrator."""
        uid   = update.effective_user.id
        text  = update.message.text.strip()

        await update.message.reply_chat_action("typing")

        agent = get_agent(uid)
        try:
            response = await agent.invoke(text)
        except Exception as e:
            response = f"Something went wrong: {e}"

        await send_response(update, response)

    # ── Build and run ─────────────────────────────────────────────

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("clear",  cmd_clear))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("mcp",    cmd_mcp))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram bot running... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    run_telegram_bot()




