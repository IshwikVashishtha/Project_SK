"""
WhatsApp Interface for DeepAgent.
Uses Meta Cloud API (webhooks) via a lightweight Flask server.

Prerequisites:
  pip install flask requests

Setup:
  1. Create a Meta App at developers.facebook.com
  2. Enable WhatsApp product and get a phone number
  3. Set in .env:
       WHATSAPP_TOKEN=<your_permanent_token>
       WHATSAPP_PHONE_ID=<your_phone_number_id>
       WHATSAPP_VERIFY_TOKEN=<any_secret_string>
  4. Expose this server publicly (e.g. with ngrok: ngrok http 5000)
  5. Register webhook URL: https://<your-ngrok>.ngrok.io/webhook

Run: python interfaces/whatsapp_bot.py
"""

from __future__ import annotations
import os, sys, json, logging
import pathfinder

from config.settings import WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_VERIFY_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_whatsapp_bot(host: str = "0.0.0.0", port: int = 5000):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("WHATSAPP_TOKEN / WHATSAPP_PHONE_ID not set in .env — WhatsApp interface disabled.")
        return

    try:
        from flask import Flask, request, jsonify
        import requests as http_requests
    except ImportError:
        print("Flask not installed. Run: pip install flask requests")
        return

    from agents.orchestrator import Orchestrator

    app = Flask(__name__)
    user_agents: dict[str, Orchestrator] = {}

    def get_agent(phone: str) -> Orchestrator:
        if phone not in user_agents:
            logger.info(f"New Orchestrator for WhatsApp user {phone}")
            user_agents[phone] = Orchestrator()
        return user_agents[phone]

    def send_whatsapp_message(to: str, body: str):
        url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }
        # Split long messages
        chunks = [body[i:i+4000] for i in range(0, len(body), 4000)]
        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": chunk},
            }
            try:
                http_requests.post(url, headers=headers, json=payload, timeout=10)
            except Exception as e:
                logger.error(f"Failed to send WA message: {e}")

    @app.route("/webhook", methods=["GET"])
    def verify():
        """Meta webhook verification handshake."""
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403

    @app.route("/webhook", methods=["POST"])
    def webhook():
        """Receive incoming WhatsApp messages."""
        data = request.get_json(silent=True) or {}
        try:
            entry   = data["entry"][0]
            changes = entry["changes"][0]
            value   = changes["value"]
            msg     = value["messages"][0]
            from_   = msg["from"]          # sender's phone number
            text    = msg["text"]["body"].strip()
        except (KeyError, IndexError):
            return jsonify({"status": "ignored"}), 200

        logger.info(f"WA message from {from_}: {text}")

        # Special commands
        if text.lower() == "/clear":
            if from_ in user_agents:
                user_agents[from_].clear_memory()
            send_whatsapp_message(from_, "Memory cleared!")
            return jsonify({"status": "ok"}), 200

        if text.lower() == "/status":
            agent = get_agent(from_)
            send_whatsapp_message(from_, agent.get_status())
            return jsonify({"status": "ok"}), 200

        # Normal message
        agent = get_agent(from_)
        try:
            response = agent.invoke(text)
        except Exception as e:
            response = f"Sorry, something went wrong: {e}"

        send_whatsapp_message(from_, response)
        return jsonify({"status": "ok"}), 200

    print(f"📱 WhatsApp bot running on http://{host}:{port}/webhook")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_whatsapp_bot()