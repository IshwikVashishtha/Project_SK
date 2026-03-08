# DeepAgent — SK v2.0

A **hierarchical multi-agent AI system** with a single orchestrator, specialist sub-agents (each with their own summarisation middleware), and three interfaces: CLI, Telegram, and WhatsApp.

---

## Architecture

```
User  ──►  Orchestrator
              │
    ┌─────────┼──────────┬──────────┬──────────┐──────────┐
    ▼         ▼          ▼          ▼          ▼          ▼
Research   Media       Data      System   Conversation    Mcp 
Agent      Agent       Agent     Agent      Agent        Agent
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
├──mcp/
│   ├── mcp_client.py
│   ├── mcp_registry.py
│      
├── agents/
│   ├── base_agent.py            # BaseSubAgent (all agents inherit this)
│   ├── orchestrator.py          # Master orchestrator  ← main router
│   ├── research_agent.py        # ResearchAgent → WebSearchAgent + WikiAgent
│   ├── media_agent.py           # MediaAgent (YouTube)
│   ├── data_agent.py            # DataAgent → MathAgent + CSVAgent
│   ├── system_agent.py          # SystemAgent (weather, time, OS)
│   ├── mcp_agent.py             # McpAgent (file system, git, fetch, memory)
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

---

## MCP Integration

DeepAgent now includes a dedicated **MCPAgent** that connects to any MCP (Model Context Protocol) server and exposes their tools to the LLM automatically.

### Updated Architecture

```
User → Orchestrator
           ├── ResearchAgent   (web + Wikipedia)
           ├── MediaAgent      (YouTube)
           ├── DataAgent       (math + CSV)
           ├── SystemAgent     (weather, time)
           ├── ConversationAgent (chat)
           └── MCPAgent  ◄── NEW
                   ├── MCPFilesystemAgent   (read/write files)
                   ├── MCPGitAgent          (git + GitHub)
                   ├── MCPCommunicationAgent(Gmail + Slack + Notion)
                   ├── MCPDatabaseAgent     (Postgres + SQLite)
                   ├── MCPBrowserAgent      (Puppeteer + Fetch)
                   └── MCPMemoryAgent       (persistent KV memory)
```

### MCP Servers Included

| Server | Capability | Needs API key? | What it does |
|---|---|---|---|
| `filesystem` | filesystem | ❌ | Read/write/search local files |
| `git` | git | ❌ | Git status, diff, commit, branch |
| `github` | git | ✅ `GITHUB_TOKEN` | Issues, PRs, search code |
| `gdrive` | gdrive | ✅ OAuth | Google Drive files/docs |
| `gmail` | gmail | ✅ OAuth | Send/read emails |
| `slack` | slack | ✅ `SLACK_BOT_TOKEN` | Post/read Slack messages |
| `notion` | notion | ✅ `NOTION_API_KEY` | Read/write Notion pages |
| `postgres` | database | ✅ `POSTGRES_URL` | SQL queries |
| `sqlite` | database | ❌ | Local SQLite queries |
| `brave_search` | search | ✅ `BRAVE_API_KEY` | Privacy-focused web search |
| `fetch` | browser | ❌ | Fetch any URL as markdown |
| `puppeteer` | browser | ❌ | Browser automation |
| `memory` | memory | ❌ | Persistent key-value store |
| `docker` | devops | ❌ | Docker container management |

### Enabling MCP Servers

**Step 1** — Install prerequisites:
```bash
pip install mcp langchain-mcp-adapters
npm install -g npx        # for npx-based servers
pip install uvx           # or: pip install uv
```

**Step 2** — Enable in `.env`:
```env
# Servers that need no API key — just toggle on:
MCP_FILESYSTEM_ENABLED=true
MCP_GIT_ENABLED=true
MCP_FETCH_ENABLED=true
MCP_MEMORY_ENABLED=true

# Servers that need credentials:
GITHUB_TOKEN=ghp_...
SLACK_BOT_TOKEN=xoxb-...
NOTION_API_KEY=secret_...
```

**Step 3** — Run as normal:
```bash
python main.py cli
```

DeepAgent will auto-detect which servers are configured and load their tools at startup.

### Adding a Custom MCP Server

Add one entry to `mcp/mcp_registry.py`:

```python
"my_server": {
    "transport":    "stdio",
    "command":      "npx",
    "args":         ["-y", "my-mcp-server-package"],
    "env":          {"MY_API_KEY": os.getenv("MY_API_KEY", "")},
    "description":  "What this server does.",
    "capability":   "my_capability",       # used for routing
    "required_env": ["MY_API_KEY"],        # must be set for auto-enable
    "enabled":      bool(os.getenv("MY_API_KEY")),
},
```

Then add keywords for it in `agents/mcp_agent.py` under `MCP_ROUTING`.

### Example MCP Commands

| You say | What happens |
|---|---|
| "Read the file at ~/notes.txt" | MCPFilesystemAgent reads the file |
| "What's the git status of my repo?" | MCPGitAgent runs `git status` |
| "Create a GitHub issue titled Bug in login" | MCPGitAgent creates issue via GitHub API |
| "Send an email to boss@company.com about the report" | MCPCommunicationAgent sends via Gmail |
| "Post 'Deploy done' in the #general Slack channel" | MCPCommunicationAgent posts to Slack |
| "Query: SELECT * FROM users LIMIT 5" | MCPDatabaseAgent runs SQL |
| "Open https://example.com and take a screenshot" | MCPBrowserAgent uses Puppeteer |
| "Remember that my preference is dark mode" | MCPMemoryAgent stores the preference |
| "What did I tell you to remember?" | MCPMemoryAgent retrieves stored info |