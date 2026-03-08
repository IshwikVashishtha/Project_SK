"""
Telegram Bot Interface for DeepAgent.
Each user gets their OWN Orchestrator instance with isolated memory.

Install dependency: pip install python-telegram-bot

Run: python interfaces/telegram_bot.py
"""

from __future__ import annotations
import os, sys, logging
import pathfinder

from config.settings import TELEGRAM_BOT_TOKEN

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

    # Per-user orchestrator instances
    user_agents: dict[int, Orchestrator] = {}

    def get_agent(user_id: int) -> Orchestrator:
        if user_id not in user_agents:
            logger.info(f"Creating new Orchestrator for user {user_id}")
            user_agents[user_id] = Orchestrator()
        return user_agents[user_id]

    # ── Handlers ──────────────────────────────

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 Hi! I'm SK, your AI assistant.\n\n"
            "I can help you with:\n"
            "  • 🔍 Research & web search\n"
            "  • 🎵 YouTube playback\n"
            "  • 🔢 Maths & data analysis\n"
            "  • 🌤 Weather & time\n"
            "  • 💬 General conversation\n\n"
            "Just type anything!"
        )

    async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Commands:\n"
            "  /start  – Welcome message\n"
            "  /clear  – Clear your conversation memory\n"
            "  /status – Show agent status\n"
            "  /help   – This message\n\n"
            "Or just chat normally!"
        )

    async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid in user_agents:
            user_agents[uid].clear_memory()
        await update.message.reply_text("Memory cleared! Fresh start.")

    async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        agent = get_agent(uid)
        await update.message.reply_text(agent.get_status())

    async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid  = update.effective_user.id
        text = update.message.text.strip()

        await update.message.reply_chat_action("typing")

        agent = get_agent(uid)
        try:
            response = agent.invoke(text)
            response = response[0]["text"]
        except Exception as e:
            response = f"Sorry, something went wrong: {e}"
        # Telegram max message length = 4096
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000])
        else:
            await update.message.reply_text(response)

    # ── Build and run app ─────────────────────

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   help_cmd))
    app.add_handler(CommandHandler("clear",  clear_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
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
                                                                            
███████╗██╗  ██╗ ██████╗     ██████╗  ╔═════════════════════════════════════╗          
██╔════╝██║ ██╔╝ ╚════██╗   ██╔═████╗ ║ DeepAgent • SK v2.0                 ║         
███████╗█████╔╝   █████╔╝   ██║██╔██║ ║ Multi-Agent AI Assistant (CLI Mode) ║          
╚════██║██╔═██╗  ██╔═══╝    ████╔╝██║ ╚═════════════════════════════════════╝         
███████║██║  ██╗ ███████╗██╗╚██████╔╝ Type your message and press Enter.         
╚══════╝╚═╝  ╚═╝ ╚══════╝╚═╝ ╚═════╝  Commands: /status /clear /help /exit              
"""
if __name__ == "__main__":
    print("\033[95m" + BIGBANNER + "\033[0m")
    run_telegram_bot()