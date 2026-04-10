# MCP Hub

> A universal CLI for connecting to multiple MCP servers and interacting with them via natural language using LLMs.

## What is This?

**MCP Hub** is a flexible CLI tool that lets you connect to any MCP (Model Context Protocol) server—whether running locally or via `uvx`—and interact with them through an AI-powered chat interface. It supports multiple LLM providers (OpenAI, Google, OpenRouter, Groq) and maintains chat history.

## Features

- **Multi-Server Support**: Connect to any number of MCP servers (local HTTP or uvx-based)
- **Dual Built-in Servers**: SQLite database operations + Filesystem operations
- **Multi-Model Support**: Use GPT, Gemini, Groq, or OpenRouter models
- **Chat History**: Persistent JSON-based conversation history (last 30 messages)
- **Universal Tools**: Any MCP tools exposed by connected servers are automatically available

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          app.py (Chat CLI)                            │
└─────────────────────────────────────────────────────────────────────┘
        │                                                │
        │  ┌──────────────────────────────────────────┐  │
        │  │    MultiServerMCPClient (mcps.py)          │  │
        │  └──────────────────────────────────────────┘  │
        │                    │                               │
   ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐ │
   │ SQLite MCP │  │  FS MCP   │  │  uvx     │  │ ...    │
   │ :8000    │  │  :8005   │  │ Tools    │  │        │
   └──────────┘  └──────────┘  └─────────┘  └────────┘
        │                                                │
        │  Multiple LLM Providers                        │
        │  (OpenAI/Google/Groq/OpenRouter)           │
        ▼                                                ▼
    User Terminal                                Your Tools/APIs
```

## Quick Start

### Prerequisites

- Python 3.11+
- API keys for your chosen LLM provider(s)

### Installation

```bash
uv sync
```

### Running with Docker (Recommended)

Start both MCP servers automatically:

```bash
docker compose up
```

Then in another terminal:

```bash
uv run app.py
```

### Running Manually

Start the MCP servers:

```bash
# Terminal 1 - SQLite server
uv run --frozen mcps.mcp_server

# Terminal 2 - Filesystem server
uv run --frozen mcps.mcp_server2

# Terminal 3 - Chat CLI
uv run app.py
```

### Configuration

Create a `.env` file:

```bash
# Required: LLM Provider (openai/google/openrouter/groq)
MODEL_PROVIDER=openai

# Provider-specific API key
OPENAI_API_KEY=sk-your-key-here
# or
GOOGLE_API_KEY=your-key
# or
OPEN_ROUTER_API_KEY=your-key
# or
GROQ_API_KEY=your-key

# Model name (optional - defaults per provider)
OPENAI_MODEL=gpt-4o
GOOGLE_MODEL=gemini-2.0-flash
OPEN_ROUTER_MODEL=x-ai/grok-4.1-fast
GROQ_MODEL=llama-3.3-70b-versatile

# Optional settings
MODEL_TEMPERATURE=0.5
MAX_TOKENS=1500

# Custom MCP server URL (optional)
DEFAULT_MCP_SERVER_URL=http://127.0.0.1:8000/mcp/
```

### Adding More MCP Servers

Edit `modules/mcps.py` to add servers:

```python
MCP_TOOLS = {
    # Local HTTP server
    "my-local-server": {
        "url": "http://127.0.0.1:8000/mcp/",
        "transport": "streamable-http",
    },
    # uvx-based server
    "duckduckgo-search": {
        "command": "uvx",
        "transport": "stdio",
        "args": ["duckduckgo-mcp-server"],
        "env": {
            "DDG_SAFE_SEARCH": "MODERATE",
            "DDG_REGION": "in-en",
        },
    },
}
```

## Built-in MCP Servers

### SQLite Server (mcp1) - Port 8000

Full SQLite database operations:

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in the database |
| `table_info` | Get schema information for a table |
| `create_table` | Create a new table with columns |
| `insert_rows` | Insert one or more rows |
| `select_rows` | Query rows with filters |
| `select_one_row` | Query a single row |
| `update_rows` | Update existing rows |
| `delete_rows` | Delete rows |
| `upsert_row` | Insert or update on conflict |
| `count_rows` | Count rows in a table |
| `delete_table` | Drop a table |
| `flush_database` | Delete all tables |
| `rename_table` | Rename a table |
| `execute_sql` | Execute raw SQL |
| `create_index` | Create an index |
| `list_indexes` | List all indexes |
| `vacuum_database` | Optimize database |

Database path: `./datastore/sqlite_ops.db`

### Filesystem Server (mcp2) - Port 8005

Full filesystem operations:

| Tool | Description |
|------|-------------|
| `list_directory` | List directory contents |
| `get_file_info` | Get file details |
| `read_file` | Read file content |
| `write_file` | Write content to file |
| `create_file` | Create a new file |
| `copy_file` | Copy file/directory |
| `move_file` | Move file/directory |
| `delete_file` | Delete file/directory |
| `create_directory` | Create a directory |
| `search_files` | Search with glob pattern |
| `exists` | Check if path exists |
| `get_size` | Get file/dir size |
| `tree` | Directory tree structure |

Root: Project directory

## Usage

```
Enter Your Query: list tables in the database
Enter Your Query: create a table users with name text age int email text
Enter Your Query: insert into users name Alice age 25
Enter Your Query: list all files in the datastore folder
Enter Your Query: show the directory tree
Enter Your Query: q
```

## Project Structure

```
sqlite-mcp/
├── app.py                      # Main chat CLI
├── pyproject.toml              # Project dependencies
├── compose.yml              # Docker services
├── Dockerfile
├── .env                   # Environment variables
├── datastore/              # Data files
│   ├── sqlite_ops.db
│   └── students.csv
├── modules/
│   ├── __init__.py
│   ├── agent_utils.py        # LLM factory
│   ├── logger.py           # Colored logging
│   ├── mcps.py            # MCP server config
│   ├── system_prompts/     # Agent system prompts
│   └── sqlite3/           # SQLite utilities
├── mcps/
│   ├── __init__.py
│   ├── mcp_server.py       # SQLite MCP server
│   └── mcp_server2.py     # Filesystem MCP server
└── chat_history.json       # Chat history (auto)
```

## Supported LLM Providers

| Provider | Env Vars Required | Models |
|----------|-------------------|--------|
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL` | gpt-4o, gpt-4o-mini, etc. |
| Google | `GOOGLE_API_KEY`, `GOOGLE_MODEL` | gemini-2.0-flash, etc. |
| OpenRouter | `OPEN_ROUTER_API_KEY`, `OPEN_ROUTER_CHAT_MODEL` | x-ai/grok-4.1-fast, etc. |
| Groq | `GROQ_API_KEY`, `GROQ_MODEL` | llama-3.3-70b-versatile, etc. |

## Chat History

- Stored in `chat_history.json`
- Keeps last 30 messages
- Automatically cleared on exit (`q`, `quit`, `exit`)
- Format: `[{"type": "human"/"ai", "data": {"content": "..."}}]`

## Roadmap

- [ ] Web UI (FastAPI/Streamlit)
- [ ] Interactive MCP server discovery
- [ ] Vector store for long-term memory
- [ ] Tool result caching
- [ ] Multi-turn tool orchestration

## Requirements

```
langchain>=1.2
langchain-core
langchain-openai
langchain-google-genai
langchain-openrouter
langchain-groq
langchain-mcp-adapters
langgraph
fastmcp
python-dotenv
loguru
colorlog
starlette
```

## License

MIT