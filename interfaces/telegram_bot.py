"""
interfaces/telegram_bot.py
════════════════════════════
Telegram Bot Interface for DeepAgent.
Each user gets their own Orchestrator instance with isolated memory.

Install: pip install python-telegram-bot
Run:     python main.py telegram
"""

from __future__ import annotations
import os
import sys
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import TELEGRAM_BOT_TOKEN
from utils.file_handler import is_file_response, extract_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_telegram_bot():
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

    user_agents: dict[int, Orchestrator] = {}

    def get_agent(user_id: int) -> Orchestrator:
        if user_id not in user_agents:
            logger.info(f"Creating new Orchestrator for user {user_id}")
            user_agents[user_id] = Orchestrator()
        return user_agents[user_id]

    # ── Response sender (text OR file) ────────────────────────────

    async def send_response(update: Update, response: str):
        """
        Send a file if the agent returned __FILE__:/path,
        otherwise send as normal text message.
        """
        if is_file_response(response):
            file_path = extract_path(response)
            if not os.path.exists(file_path):
                await update.message.reply_text(
                    f"I tried to send '{os.path.basename(file_path)}' "
                    f"but couldn't find it at: {file_path}"
                )
                return
            try:
                with open(file_path, "rb") as f:
                    await update.message.reply_document(
                        document=f,
                        filename=os.path.basename(file_path),
                        caption=f"Here's your file: {os.path.basename(file_path)}",
                    )
            except Exception as e:
                await update.message.reply_text(
                    f"Found the file but couldn't send it: {e}"
                )
        else:
            # Plain text — split if over Telegram's 4096 char limit
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)

    # ── Command handlers ──────────────────────────────────────────

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 Hi! I'm SK, your AI assistant.\n\n"
            "I can help you with:\n"
            "  • 🔍 Research & web search\n"
            "  • 🎵 YouTube playback\n"
            "  • 🌤 Weather & time\n"
            "  • 📁 Files — send, find, or create any file\n"
            "  • 🔧 MCP tools (git, GitHub, email, Slack, DB...)\n"
            "  • 💬 General conversation\n\n"
            "Just type anything!"
        )

    async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Commands:\n"
            "  /start   – Welcome message\n"
            "  /clear   – Clear your conversation memory\n"
            "  /status  – Show all agent status\n"
            "  /mcp     – Show MCP server status\n"
            "  /help    – This message\n\n"
            "File examples:\n"
            '  "Send me report.csv from Desktop"\n'
            '  "Create a JSON file with planets data"\n'
            '  "Find config.py in my projects folder"\n'
        )

    async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid in user_agents:
            user_agents[uid].clear_memory()
        await update.message.reply_text("Memory cleared! Fresh start.")

    async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid   = update.effective_user.id
        agent = get_agent(uid)
        await update.message.reply_text(agent.get_status())

    async def mcp_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid   = update.effective_user.id
        agent = get_agent(uid)
        await update.message.reply_text(agent.mcp_agent.get_status())

    # ── Main message handler ──────────────────────────────────────

    async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid  = update.effective_user.id
        text = update.message.text.strip()

        await update.message.reply_chat_action("typing")

        agent = get_agent(uid)
        try:
            response = agent.invoke(text)   # always returns a plain str
        except Exception as e:
            logger.error(f"Orchestrator error for user {uid}: {e}")
            response = f"Sorry, something went wrong: {e}"

        await send_response(update, response)

    # ── Build and run ─────────────────────────────────────────────

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   help_cmd))
    app.add_handler(CommandHandler("clear",  clear_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("mcp",    mcp_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram bot is running... Press Ctrl+C to stop.")
    app.run_polling()


BIGBANNER = """
███████╗██╗  ██╗    ███╗   ███╗██╗    █████╗ ███╗   ███╗ ██████╗ ██████╗
██╔════╝██║ ██╔╝    ████╗ ████║██║   ██╔══██╗████╗ ████║██╔═══██╗██╔══██╗
███████╗█████╔╝     ██╔████╔██║██║   ███████║██╔████╔██║██║   ██║██████╔╝
╚════██║██╔═██╗     ██║╚██╔╝██║██║   ██╔══██║██║╚██╔╝██║██║   ██║██╔══██╗
███████║██║  ██╗    ██║ ╚═╝ ██║██║   ██║  ██║██║ ╚═╝ ██║╚██████╔╝██║  ██║
╚══════╝╚═╝  ╚═╝    ╚═╝     ╚═╝╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝
"""


if __name__ == "__main__":
    print("\033[95m" + BIGBANNER + "\033[0m")
    run_telegram_bot()