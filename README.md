# MCP Hub

<div align="center">

**A Universal AI Agent Platform — Give Your LLM Hands to Interact with the Real World**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?logo=langchain&logoColor=white)](https://www.langchain.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B6B?logo=chromadb&logoColor=white)](https://www.trychroma.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Quick Start](#-quick-start) · [Architecture](#-architecture) · [API Docs](#-api-reference) · [Contributing](#-contributing)

</div>

---

## What is MCP Hub?

**MCP Hub** is an AI agent framework that connects Large Language Models (LLMs) to the real world through the **Model Context Protocol (MCP)** and **LangChain** tools.

Think of it as giving your AI **hands** — instead of just generating text, it can now:

- Query and manage **SQLite databases**
- Read, write, and organize **files**
- **Download** files from the internet
- **Search the web** for live information
- **Send emails** and **schedule tasks**
- **Index documents** for AI-powered semantic search
- **Embed & search** any file (PDF, MD, CSV, DOCX, etc.) or **webpage URL** using local ChromaDB vector store
- Check **weather** and **timezones**

> **MCP (Model Context Protocol)** is an open standard that lets AI models securely connect to external data sources and tools. MCP Hub implements this standard using [FastMCP](https://github.com/jlowin/fastmcp) servers and LangChain adapters.

### See It in Action

```
You: "Create a users table with name, age, and email columns"
AI:  ✅ Created table 'users' with columns: name (TEXT), age (INTEGER), email (TEXT)

You: "Embed this PDF and tell me the key findings"
AI:  📄 Embedded report.pdf → 47 chunks stored in ChromaDB
     🔍 Based on the document, the key findings are...

You: "Search the web for latest AI breakthroughs"
AI:  🔍 Found 5 results... [summarizes live web search results]

You: "Download https://example.com/report.pdf"
AI:  ⬇️ Downloaded report.pdf (2.4 MB) to ./datastore/downloads/

You: "Send an email to my boss saying the project is complete"
AI:  📧 Email queued! Job ID: abc-123-xyz (check status anytime)
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com/) | High-performance async API & web UI |
| **AI Framework** | [LangChain](https://www.langchain.com/) + [LangGraph](https://langchain-ai.github.io/langgraph/) | LLM orchestration & agent logic |
| **MCP Protocol** | [FastMCP](https://github.com/jlowin/fastmcp) + [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters) | Model Context Protocol servers |
| **Vector Store** | [ChromaDB](https://www.trychroma.com/) + [langchain-chroma](https://github.com/langchain-ai/langchain-chroma) | Local embedding storage & semantic search |
| **Background Jobs** | [Huey](https://huey.readthedocs.io/) + [Redis/Valkey](https://valkey.io/) | Async task queue & scheduling |
| **LLM Providers** | OpenAI, Google Gemini, Groq, OpenRouter, NVIDIA | Multi-provider AI model support |
| **Embedding Providers** | OpenAI, Google, OpenRouter, NVIDIA | Multi-provider embedding model support |
| **Database** | SQLite3 | Lightweight, serverless relational DB |
| **Package Manager** | [uv](https://docs.astral.sh/uv/) | Ultra-fast Python package management |
| **Container** | Docker + Docker Compose | Production-ready containerization |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│              ┌─────────────────────────────────┐                │
│              │   Dark-themed Chat UI (HTML/JS) │                │
│              │   ├─ Real-time chat stream      │                │
│              │   ├─ Syntax-highlighted code    │                │
│              │   ├─ JSON pretty-printing       │                │
│              │   └─ Toast notifications        │                │
│              └─────────────────────────────────┘                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/WebSocket
┌──────────────────────────▼──────────────────────────────────────┐
│                     FASTAPI APPLICATION (port 8001)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  /api/chat   │  │ /api/history │  │   /api/health        │  │
│  │  POST        │  │ GET / POST   │  │   GET                │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                           │                                     │
│              ┌────────────▼────────────┐                        │
│              │    MCPAgentModule       │                        │
│              │  ┌───────────────────┐  │                        │
│              │  │  System Prompt    │  │                        │
│              │  │  Chat History     │  │                        │
│              │  │  LLM Instance     │  │                        │
│              │  └───────────────────┘  │                        │
│              └────────────┬────────────┘                        │
└───────────────────────────┼─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼──────┐  ┌────────▼────────┐  ┌──────▼───────┐
│  MCP Servers │  │  LangChain Tools │  │   LLM APIs   │
│  (Tools)     │  │  (Background)    │  │  (Providers) │
├──────────────┤  ├─────────────────┤  ├──────────────┤
│ sqlite-local │  │ index_files     │  │ OpenAI       │
│ downloader   │  │ index_urls      │  │ Google       │
│ ddg-search   │  │ send_email_task │  │ Groq         │
│ fetch        │  │ schedule_task   │  │ OpenRouter   │
│ time         │  │ get_system_time │  │ NVIDIA       │
│ pageindex    │  │ weather_tool    │  └──────────────┘
│ url-downloader│  │ file_management │
└──────────────┘  │ embed_file      │
                  │ query_embedded  │
                  │ chroma_manage   │
                  └─────────────────┘
        │                   │
        └───────────┬───────┘
                    │
┌───────────────────▼──────────────────────┐
│         BACKGROUND WORKER (Huey)         │
│  ┌────────────────────────────────────┐  │
│  │  Redis/Valkey Queue (port 6379)    │  │
│  │  ├─ Document Indexing (PageIndex)  │  │
│  │  ├─ Email Sending (SMTP)           │  │
│  │  ├─ Task Scheduling (delay/ETA)    │  │
│  │  └─ Sleep/Delay Tasks              │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### Data Flow

1. **User** sends a message via the web UI or API
2. **FastAPI** receives it and passes to `MCPAgentModule`
3. **Agent** loads the system prompt, chat history, and available tools
4. **LLM** reasons about which tools to call and in what order
5. **Tools** execute — some are local (file ops), some call external MCP servers, some queue background jobs, some embed & search documents
6. **Response** streams back to the user with results, job IDs for async tasks, or direct answers

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- At least one LLM API key (OpenAI, Google, Groq, OpenRouter, or NVIDIA)

### Step 1: Clone & Configure

```bash
git clone https://github.com/your-repo/mcp-hub.git
cd mcp-hub
cp .env.sample .env
```

Edit `.env` and add your API keys:

```bash
# Choose your AI provider: openai | google | groq | openrouter | nvidia
MODEL_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o

# Choose your embedding provider (for ChromaDB vector search)
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDINGS_MODEL=text-embedding-3-small

# Optional but recommended
PAGE_INDEX_API_KEY=your-pageindex-key
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### Step 2: Launch Everything

```bash
docker compose up
```

This starts 5 services:

| Service | Port | What It Does |
|---------|------|--------------|
| `valkey` | 6379 | Redis-compatible task queue & cache |
| `mcp_sql` | 8000 | SQLite MCP server (database ops) |
| `mcp_downloader` | 8010 | File download MCP server |
| `huey` | — | Background task worker |
| `app` | 8001 | **Main FastAPI web app & chat UI** |

### Step 3: Open the App

Navigate to **http://localhost:8001**

You should see the MCP Hub chat interface with a status indicator showing **Online**.

### Step 4: Try Your First Commands

> Click any suggestion pill in the UI, or type:

- `"What tools do you have?"`
- `"Create a table called todos with title TEXT and done INTEGER"`
- `"Embed this file: ./datastore/docs/report.pdf"`
- `"What are the main findings in the embedded document?"`
- `"Search the web for Python 3.13 new features"`
- `"What's the weather in Tokyo?"`

---

## Local Development (Without Docker)

If you prefer running natively for development or debugging:

### Prerequisites

- Python 3.11–3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- Redis or Valkey running locally

### Setup

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Start Redis/Valkey (if not running)
# docker run -d -p 6379:6379 --name valkey bitnami/valkey:latest

# Start the SQLite MCP server (terminal 1)
python -m mcps.mcp_sql

# Start the Downloader MCP server (terminal 2)
python -m mcps.mcp_downloader

# Start the Huey worker (terminal 3)
huey_consumer tasks.tasks.huey -k thread -w 2

# Start the main app (terminal 4)
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

---

## Project Structure

```
mcp-hub/
├── app.py                          # FastAPI entry point & API routes
├── compose.yml                     # Docker Compose orchestration
├── Dockerfile                      # Container image (Python 3.13 + uv)
├── pyproject.toml                  # Python dependencies & project metadata
├── .env / .env.sample              # Environment configuration
│
├── mcps/                           # MCP Servers (Model Context Protocol)
│   ├── __init__.py                 # MCP_TOOLS registry & configuration
│   ├── mcp_sql.py                  # SQLite MCP server (port 8000)
│   ├── mcp_fs.py                   # Filesystem MCP server (port 8005)
│   └── mcp_downloader.py          # Downloader MCP server (port 8010)
│
├── modules/                        # Core application modules
│   ├── __init__.py                 # Module exports
│   ├── agent_mod.py                # MCPAgentModule: orchestrates LLM + tools
│   ├── agent_utils.py              # LLM factory (OpenAI, Google, Groq, OpenRouter)
│   ├── embedder.py                 # Embedding factory + ChromaDB pipeline
│   ├── logger.py                   # Colorized logging utility
│   │
│   ├── tools/                      # LangChain tools (split by category)
│   │   ├── __init__.py             # Re-exports all tools + get_vectorless_tools()
│   │   ├── background.py           # Task queue tools (index, email, schedule, sleep)
│   │   ├── datetime.py             # System datetime tool
│   │   ├── embedding.py            # ChromaDB tools (embed, query, manage)
│   │   ├── file_management.py      # File ops (read, write, copy, move, delete)
│   │   └── weather.py              # OpenWeatherMap tool
│   │
│   ├── system_prompts/
│   │   ├── general_prompt.py       # Main AI system instructions
│   │   └── local_mcp_sqlit3_prompt.py  # SQLite-specific prompt
│   │
│   └── sqlite3/
│       ├── sqlite_1.py             # SQLiteUtils (used by MCP SQL server)
│       ├── sqlite_2.py             # SQLiteManager (alternative impl)
│       └── sqlite_3.py             # SQLiteDB (modern WAL + transactions)
│
├── tasks/                          # Background task definitions (Huey)
│   ├── __init__.py                 # Task exports
│   └── tasks.py                    # index_documents, send_email, schedule, etc.
│
├── templates/
│   └── index.html                  # Dark glassmorphism chat UI
│
└── datastore/                      # Persistent data storage
    ├── internal/                   # SQLite DB, chat history, ChromaDB
    │   └── chroma/                 # Vector embeddings (auto-created)
    └── downloads/                  # Downloaded files
```

---

## Embedding & Vector Search

MCP Hub includes a built-in **local embedding pipeline** powered by ChromaDB. Embed any file or webpage, then search it semantically.

### Supported File Formats

| Format | Extensions | Loader |
|--------|-----------|--------|
| PDF | `.pdf` | PyPDFLoader |
| Markdown | `.md`, `.markdown` | UnstructuredMarkdownLoader |
| CSV | `.csv` | CSVLoader |
| Text | `.txt` | TextLoader |
| JSON | `.json` | JSONLoader |
| Word | `.docx`, `.doc` | Docx2txtLoader |
| HTML | `.html`, `.htm` | UnstructuredHTMLLoader |
| XML | `.xml` | UnstructuredXMLLoader |
| Web URLs | `http://...`, `https://...` | WebBaseLoader |

### How It Works

```
File/URL → Load → Chunk (1000 chars, 200 overlap) → Embed → Store in ChromaDB
                                                           ↓
Query → Embed query → Similarity search → Return top-k chunks
```

### Example Usage

```bash
# Embed a PDF
You: "Embed ./datastore/docs/quarterly-report.pdf"
AI:  ✅ Stored 47 chunks in ChromaDB collection 'default'

# Search embedded content
You: "What does the report say about revenue?"
AI:  🔍 Based on the embedded document, Q3 revenue grew 23%...

# Embed a webpage
You: "Embed https://example.com/article"
AI:  ✅ Stored 12 chunks in ChromaDB collection 'default'

# Manage collections
You: "List all my embedded collections"
AI:  📚 Collections: default (47 items), reports (120 items)

You: "Clear the default collection"
AI:  🗑️ Cleared 47 items from collection 'default'
```

### Embedding Providers

| Provider | Default Model | Env Var |
|----------|--------------|---------|
| **OpenAI** | `text-embedding-3-small` | `OPENAI_EMBEDDINGS_MODEL` |
| **Google** | — | `GOOGLE_EMBEDDINGS_MODEL` |
| **OpenRouter** | `openai/text-embedding-3-small` | `OPEN_ROUTER_EMBEDDINGS_MODEL` |
| **NVIDIA** | — | `NVIDIA_EMBEDDINGS_MODEL` |

Set `EMBEDDING_PROVIDER` in `.env` to choose. ChromaDB data persists at `./datastore/internal/chroma/`.

---

## Configuration Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MODEL_PROVIDER` | LLM provider to use | `openai`, `google`, `groq`, `openrouter`, `nvidia` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `GOOGLE_API_KEY` | Google Gemini key | `...` |
| `GROQ_API_KEY` | Groq API key | `gsk_...` |
| `OPEN_ROUTER_API_KEY` | OpenRouter key | `sk-or-v1-...` |
| `NVIDIA_API_KEY` | NVIDIA AI Endpoints key | `nvapi-...` |
| `REDIS_URL` | Redis/Valkey connection URL | `redis://:testpass@valkey:6379/0` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EMBEDDING_PROVIDER` | Embedding model provider | `openai` |
| `MODEL_TEMPERATURE` | Creativity/randomness (0–1) | `0.4` |
| `MAX_TOKENS` | Max response length | `1500` |
| `PAGE_INDEX_API_KEY` | PageIndex API for document search | — |
| `EMAIL_HOST_USER` | SMTP email address | — |
| `EMAIL_HOST_PASSWORD` | SMTP app password | — |
| `OPENWEATHERMAP_API_KEY` | Weather API key | — |
| `DATASTORE_DIR` | Root data directory | `./datastore` |
| `SQLITE_DB_PATH` | SQLite database file path | `./datastore/internal/sqlite3.db` |
| `CHROMA_DIR` | ChromaDB persist directory | `./datastore/internal/chroma` |

### Provider-Specific Models

| Provider | Default Model | Notes |
|----------|--------------|-------|
| **OpenAI** | `gpt-4o` | Most capable, reliable tool use |
| **Google** | `gemini-2.5-flash` | Fast, good for coding |
| **Groq** | `openai/gpt-oss-120b` | Free tier available, very fast |
| **OpenRouter** | `baidu/ernie-4.5-21b-a3b` | Access to 100+ models |
| **NVIDIA** | `qwen/qwen3.5-122b-a10b` | NVIDIA AI Endpoints |

---

## Complete Tool Catalog

### MCP Servers (Real-Time Tools)

These tools execute immediately and return results directly to the LLM.

| Tool | Server | What It Does |
|------|--------|--------------|
| `sqlite-local` | `mcp_sql` | **Full SQLite CRUD**: list tables, create tables, insert/select/update/delete rows, raw SQL, indexes, vacuum |
| `downloader` | `mcp_downloader` | Download files from URLs with progress tracking, batch downloads, URL metadata checking |
| `ddg-search` | stdio | Web search via DuckDuckGo with region/safe-search config |
| `fetch` | stdio | Fetch and extract text content from any webpage |
| `time` | stdio | Get current time for any timezone |
| `pageindex` | HTTP | Query indexed documents using semantic AI search |
| `url-downloader` | stdio | Alternative downloader with custom output path |

### LangChain Tools — Background & Scheduling

| Tool | Type | What It Does |
|------|------|--------------|
| `index_files` | Background | Index local files (PDF, MD, TXT, CSV) to PageIndex for AI search. Returns **job ID**. |
| `index_urls` | Background | Index remote URLs to PageIndex. Returns **job ID**. |
| `send_email_task` | Background | Queue email via SMTP. Returns **job ID**. |
| `schedule_task` | Background | Schedule any Huey task to run after delay or at specific ETA. Returns **job ID**. |
| `get_background_task_status` | Utility | Check status of any background task by job ID |
| `get_all_tasks` | Utility | List all queued, scheduled, and completed tasks |
| `get_system_datetime` | Utility | Get current system time (critical for scheduling) |
| `weather_tool` | Utility | Get weather for any location via OpenWeatherMap |
| `sleep` | Background | Queue a sleep/delay task for testing |

### LangChain Tools — Embedding & Vector Store (ChromaDB)

| Tool | Type | What It Does |
|------|------|--------------|
| `embed_file` | Embedding | Embed a file or URL into local ChromaDB. Supports PDF, MD, CSV, TXT, JSON, DOCX, HTML, XML, and web URLs. |
| `query_embedded_data` | Retrieval | Semantic search over embedded documents. Returns top-k matching chunks with metadata. |
| `list_chroma_collections` | Management | List all ChromaDB collections and their document counts |
| `clear_chroma_collection` | Management | Remove all documents from a collection (keeps the collection) |
| `delete_chroma_collection` | Management | Permanently delete an entire collection and its data |

### LangChain Tools — File Management

From `FileManagementToolkit` (sandboxed to `DATASTORE_DIR`):

`read_file`, `write_file`, `copy_file`, `move_file`, `delete_file`, `list_directory`, `make_directory`, `move_directory`

### SQLite Operations Detail

The `sqlite-local` MCP server provides these specific operations:

- `list_tables` — List all tables
- `table_info` — Get schema for a table
- `create_table` — Create with columns, primary key, unique constraints
- `insert_rows` — Insert single or multiple rows
- `select_rows` — Query with WHERE, ORDER BY, LIMIT, OFFSET, DISTINCT
- `select_one_row` — Get first matching row
- `update_rows` — Update with WHERE clause
- `delete_rows` — Delete with WHERE clause
- `upsert_row` — Insert or update on conflict
- `count_rows` — Count with optional filters
- `execute_sql` — Run raw SQL (SELECT, PRAGMA, INSERT, etc.)
- `create_index` / `list_indexes` — Index management
- `delete_table` / `rename_table` / `flush_database` — Schema changes
- `vacuum_database` — Reclaim storage space
- `active_database` — Show current DB path

---

## API Reference

All endpoints return JSON. The web UI is served at the root path.

| Endpoint | Method | Body / Params | Response | Description |
|----------|--------|---------------|----------|-------------|
| `/` | GET | — | HTML | Chat web interface |
| `/ping` | GET | — | `{"status":"ok","agent_ready":true}` | Health check |
| `/api/chat` | POST | `{"message":"..."}` | `{"response":"..."}` | Send a message to the AI agent |
| `/api/history` | GET | — | `{"history":[...]}` | Get conversation history |
| `/api/clear` | POST | — | `{"status":"ok"}` | Clear chat history |
| `/api/health` | GET | — | `{"status":"healthy",...}` | Detailed health status |
| `/docs` | GET | — | HTML | Auto-generated Swagger UI |

### Example API Usage

```bash
# Chat with the agent
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is it in Tokyo?"}'

# Get history
curl http://localhost:8001/api/history

# Clear history
curl -X POST http://localhost:8001/api/clear
```

---

## Extending MCP Hub

### Adding a Custom MCP Server

Edit `mcps/__init__.py` and add to the `MCP_TOOLS` dictionary:

**HTTP-based server:**
```python
"my-server": {
    "url": "http://127.0.0.1:9000/mcp/",
    "transport": "streamable-http",
}
```

**STDIO-based server (via uv):**
```python
"my-uvx-server": {
    "command": "uv",
    "transport": "stdio",
    "args": ["run", "package-name"],
}
```

Restart the app container to pick up changes:
```bash
docker compose restart app
```

### Adding a Custom LangChain Tool

Create or edit a file in `modules/tools/`:

```python
# modules/tools/my_tool.py
from langchain.tools import tool

@tool("my_awesome_tool")
def my_awesome_tool(param: str) -> dict:
    """Description for the AI — this tells the LLM when to use this tool."""
    return {"result": "success", "param": param}
```

Then import and add it to `get_vectorless_tools()` in `modules/tools/__init__.py`.

### Adding a New Huey Background Task

Edit `tasks/tasks.py`:

```python
@huey.task(retries=3, retry_delay=5)
def my_background_task(data: str) -> str:
    logger.info(f"Processing: {data}")
    # Do work here...
    return "done"
```

Export it in `tasks/__init__.py` and register it in `schedule_task()`'s `task_map` if you want it schedulable.

---

## Docker Operations

```bash
# Start all services
docker compose up

# Start in background (detached)
docker compose up -d

# View logs
docker compose logs -f

# View logs for a specific service
docker compose logs -f app

# Stop everything
docker compose down

# Rebuild after dependency changes
docker compose build --no-cache

# Restart a single service
docker compose restart app
```

---

## Troubleshooting

### "Connection refused" errors

```bash
# Check which containers are running
docker compose ps

# Check a specific service's logs
docker compose logs mcp_sql
docker compose logs huey
```

### "API key not found"

```bash
# Verify .env file exists and has keys
cat .env

# Restart after editing .env
docker compose down && docker compose up -d
```

### "Tool not found" or MCP errors

- Verify the tool is registered in `mcps/__init__.py` or `modules/tools/`
- Rebuild containers: `docker compose build --no-cache`
- Check MCP server health: `curl http://localhost:8000/health`

### "Redis connection failed"

```bash
# Check Valkey status
docker compose logs valkey

# Verify REDIS_URL matches valkey password in compose.yml
docker compose exec valkey valkey-cli -a testpass ping
```

### Background tasks never complete

- Ensure the `huey` worker container is running: `docker compose ps huey`
- Check Huey logs: `docker compose logs huey`
- Verify Redis URL in `.env` is correct

### Embedding / ChromaDB issues

- ChromaDB data persists at `./datastore/internal/chroma/` — deleting this folder resets embeddings
- Ensure `EMBEDDING_PROVIDER` is set and the corresponding API key is valid
- Check `list_chroma_collections` to verify collections exist

---

## Security Notes

- **Never commit `.env`** — it's in `.gitignore` by default
- Store API keys securely; rotate them regularly
- The app container runs in an isolated Docker network (`caddy`)
- Database is stored locally in `datastore/` (add to backups)
- File system access is sandboxed to `DATASTORE_DIR`
- ChromaDB embeddings are stored locally — no data leaves your server (except API calls to embedding providers)
- Use strong Redis passwords in production (change `testpass` in `compose.yml`)

---

## Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** with clear, concise code
4. **Test locally** using the Docker setup
5. **Submit a Pull Request** with a detailed description

### Code Style

- Follow PEP 8 conventions
- Use type hints where practical
- Add docstrings to public functions
- Keep functions focused and modular
- Place new tools in the appropriate `modules/tools/` file

---

## License

[MIT License](LICENSE) — Built with FastMCP, LangChain, FastAPI, ChromaDB, and Huey.

---

<div align="center">

**Made with curiosity and caffeine**

If MCP Hub helps you build something cool, give it a star!

</div>
