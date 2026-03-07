# DeepAgent — SK v2.0

A **hierarchical multi-agent AI system** with a single orchestrator, specialist sub-agents (each with their own summarisation middleware), and three interfaces: CLI, Telegram, and WhatsApp.

---

## Architecture

```
User  ──►  Orchestrator
              │
    ┌─────────┼──────────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼          ▼
Research   Media       Data      System   Conversation
Agent      Agent       Agent     Agent      Agent
│                      │
├─ WebSearchAgent    ├─ MathAgent
└─ WikiAgent         └─ CSVAgent
```

**Every agent has its own `SummarizationMiddleware`** that keeps a rolling buffer of recent turns plus a compressed summary — so no agent's context ever grows unbounded.

---

## Project Structure

```
deep_agent/
├── main.py                      # Entry point  (cli | telegram | whatsapp)
├── universal_llm.py             # Multi-provider LLM wrapper
├── yt_control.py                # YouTube Selenium controller
├── requirements.txt
├── .env.template                # Copy to .env and fill in keys
│
├── config/
│   └── settings.py              # LLM assignments per agent, API keys
│
├── middleware/
│   └── summarizer.py            # SummarizationMiddleware (per-agent memory)
│
├── agents/
│   ├── base_agent.py            # BaseSubAgent (all agents inherit this)
│   ├── orchestrator.py          # Master orchestrator  ← main router
│   ├── research_agent.py        # ResearchAgent → WebSearchAgent + WikiAgent
│   ├── media_agent.py           # MediaAgent (YouTube)
│   ├── data_agent.py            # DataAgent → MathAgent + CSVAgent
│   ├── system_agent.py          # SystemAgent (weather, time, OS)
│   └── conversation_agent.py    # ConversationAgent (chat fallback)
│
├── interfaces/
│   ├── cli.py                   # Terminal interface
│   ├── telegram_bot.py          # Telegram bot
│   └── whatsapp_bot.py          # WhatsApp Meta Cloud API webhook
│
└── memory_store/                # Auto-created; holds per-agent JSON memories
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.template .env
# Edit .env and fill in OLLAMA_BASE_URL, API keys, etc.
```

### 3. Pull Ollama models

```bash
ollama pull gemma2:2b
ollama pull phi3
```

### 4. Run

```bash
# CLI (local terminal)
python main.py cli

# Telegram bot
python main.py telegram

# WhatsApp webhook
python main.py whatsapp
```

---

## Changing Which LLM Each Agent Uses

Edit `config/settings.py` (or the matching `.env` variables):

```python
AGENT_LLM_CONFIG = {
    "orchestrator": {"provider": "openai",    "model": "gpt-4o"},
    "research":     {"provider": "groq",      "model": "llama3-8b-8192"},
    "media":        {"provider": "ollama",    "model": "phi3"},
    "data":         {"provider": "ollama",    "model": "phi3"},
    "system":       {"provider": "ollama",    "model": "phi3"},
    "summarizer":   {"provider": "ollama",    "model": "phi3"},
}
```

Any provider supported by `UniversalLLM` works: `ollama`, `openai`, `anthropic`, `google_gemini`, `groq`, `azure_openai`, `openrouter`, `custom_openai`.

---

## Capabilities

| What you say              | Agent triggered     | What happens                          |
|---------------------------|---------------------|---------------------------------------|
| "What is quantum computing?" | ResearchAgent → WikiAgent | Wikipedia lookup + summary     |
| "Latest news about AI"    | ResearchAgent → WebSearchAgent | SerpAPI search             |
| "Play Arijit Singh"       | MediaAgent          | YouTube opens and plays               |
| "Skip the ad"             | MediaAgent          | Selenium clicks Skip Ad               |
| "What is 5 factorial?"    | DataAgent → MathAgent | `math.factorial(5)` = 120           |
| "Convert 100 km to miles" | DataAgent → MathAgent | Unit conversion                     |
| "Analyse sales.csv"       | DataAgent → CSVAgent | Pandas stats on the file             |
| "Weather in Meerut"       | SystemAgent         | OpenWeatherMap API call               |
| "What time is it?"        | SystemAgent         | Local datetime                        |
| "Tell me a joke"          | ConversationAgent   | Friendly chat                         |

---

## Memory System

Each agent maintains two layers of memory (stored in `memory_store/`):

- **Buffer** — last 6 conversation turns verbatim
- **Running Summary** — compressed history of older turns (done by the summarizer LLM)

When the buffer exceeds 10 turns, it's compressed into the summary and the buffer is trimmed. This ensures the context sent to the LLM stays small regardless of conversation length.

---

## Telegram Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and get a token
2. Set `TELEGRAM_BOT_TOKEN=...` in `.env`
3. Run `python main.py telegram`

## WhatsApp Setup

1. Create a Meta Developer App with WhatsApp product
2. Set `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_VERIFY_TOKEN` in `.env`
3. Run `python main.py whatsapp`
4. Expose port 5000 publicly (e.g. `ngrok http 5000`)
5. Register webhook URL in Meta dashboard: `https://your-ngrok-url/webhook`