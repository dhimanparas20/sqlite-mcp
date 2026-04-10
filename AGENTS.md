# AGENTS.md - AI Agent Guidelines

This document provides context for AI agents working on this codebase.

## Project Overview

**Project Name**: MCP Hub  
**Type**: CLI tool with embedded MCP servers  
**Core Functionality**: Universal MCP server connector with LLM-powered chat interface with built-in SQLite and Filesystem MCP servers  
**Status**: Production-ready

## Architecture

MCP Hub connects to multiple MCP servers and exposes their tools via LangChain agents:

```
app.py (Chat CLI)
       │
       ├── MultiServerMCPClient (modules/mcps.py)
       │
       ├── Built-in MCP Servers:
       │   ├── mcps/mcp_server.py (SQLite - port 8000)
       │   └── mcps/mcp_server2.py (Filesystem - port 8005)
       │
       └── create_llm → LLM (OpenAI/Google/Groq/OpenRouter)
```

### Key Files

| File | Purpose |
|------|---------|
| `app.py` | Main chat CLI with history management |
| `modules/__init__.py` | Exports `create_llm`, prompts, logger |
| `modules/mcps.py` | MCP server configurations |
| `modules/agent_utils.py` | LLM factory for multiple providers |
| `modules/logger.py` | Colored logging setup |
| `modules/system_prompts/` | Agent system prompts |
| `mcps/__init__.py` | MCP_TOOLS configuration |
| `mcps/mcp_server.py` | SQLite MCP server (FastMCP) |
| `mcps/mcp_server2.py` | Filesystem MCP server (FastMCP) |

## MCP Server Configuration

**File**: `modules/mcps.py`

Servers are defined in `MCP_TOOLS` dict with these transport types:

### 1. HTTP-based (streamable-http)
```python
"server-name": {
    "url": "http://127.0.0.1:8000/mcp/",
    "transport": "streamable-http",
}
```

### 2. STDIO-based (uvx)
```python
"server-name": {
    "command": "uvx",
    "transport": "stdio",
    "args": ["package-name"],
    "env": {"KEY": "value"},  # optional
}
```

## Default Configured Servers

```python
MCP_TOOLS = {
    "sqlite-local": {
        "url": "http://127.0.0.1:8000/mcp/",
        "transport": "streamable-http",
    },
    "custom-fs": {
        "url": "http://127.0.0.1:8005/mcp",
        "transport": "streamable-http",
    },
    "ddg-search": {...},
    "fetch": {...},
    "git": {...},
    "time": {...},
}
```

## LLM Providers

**File**: `modules/agent_utils.py`

Supported providers via `MODEL_REGISTRY`:

| Provider | Env Vars | Config |
|----------|----------|--------|
| `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` | langchain_openai.ChatOpenAI |
| `google` | `GOOGLE_API_KEY`, `GOOGLE_MODEL` | langchain_google_genai.ChatGoogleGenerativeAI |
| `openrouter` | `OPEN_ROUTER_API_KEY`, `OPEN_ROUTER_CHAT_MODEL` | langchain_openrouter.ChatOpenRouter |
| `groq` | `GROQ_API_KEY`, `GROQ_MODEL` | langchain_groq.ChatGroq |

### Using `create_llm`

```python
from modules import create_llm

llm = create_llm(
    model_provider="openai",      # or "google", "openrouter", "groq"
    model_name="gpt-4o",
    model_temperature=0.5,
    max_tokens=1500,
)
```

## Built-in MCP Servers

### SQLite Server (mcps/mcp_server.py)

Runs on port 8000. Database: `./datastore/sqlite_ops.db`

**Tools**:
- `list_tables` - List all tables
- `table_info(table_name)` - Get schema
- `create_table(table_name, columns, if_not_exists, primary_key, unique)` - Create table
- `insert_rows(data, table_name)` - Insert rows
- `select_rows(table_name, columns, where, order_by, limit, offset, distinct)` - Query rows
- `select_one_row(table_name, columns, where, order_by)` - Query single row
- `update_rows(table_name, data, where)` - Update rows
- `delete_rows(table_name, where)` - Delete rows
- `upsert_row(table_name, data, conflict_columns, update_columns)` - Upsert
- `count_rows(table_name, where)` - Count rows
- `active_database()` - Get current DB path
- `delete_table(table_name)` - Drop table
- `flush_database()` - Drop all tables
- `rename_table(table_name, new_table_name)` - Rename table
- `execute_sql(sql, params)` - Raw SQL
- `create_index(index_name, table_name, columns, unique, if_not_exists)` - Create index
- `list_indexes()` - List indexes
- `vacuum_database()` - Optimize DB

### Filesystem Server (mcps/mcp_server2.py)

Runs on port 8005. Root: Project directory

**Tools**:
- `list_directory(path, pattern, include_hidden)` - List directory
- `get_file_info(path)` - File details
- `read_file(path, max_size)` - Read content
- `write_file(path, content, create_dirs)` - Write content
- `create_file(path, content, create_dirs)` - Create file
- `copy_file(source, destination, overwrite)` - Copy
- `move_file(source, destination, overwrite)` - Move
- `delete_file(path)` - Delete
- `create_directory(path, parents)` - Create directory
- `search_files(root, pattern, max_results)` - Glob search
- `exists(path)` - Check existence
- `get_size(path)` - Get size
- `get_cwd()` - Get working directory
- `list_dir(path)` - List directory
- `path_info(path)` - Path details
- `get_pwd()` - Print working directory
- `tree(path, max_depth, include_hidden)` - Directory tree

## System Prompts

**File**: `modules/system_prompts/`

Two prompts available:

1. `LOCAL_MCP_SQLITE3_PROMPT` - SQLite-focused (for database operations)
2. `GENERAL_PROMPT` - General purpose (for all tools)

### Using Prompts

```python
from modules import LOCAL_MCP_SQLITE3_PROMPT, GENERAL_PROMPT

# Default is GENERAL_PROMPT
await agent.init(model_provider="openai", system_message=GENERAL_PROMPT)
```

## Chat History

**File**: `app.py`

- Stored in `chat_history.json` (JSON format)
- Keeps last 30 messages (was 20)
- Loaded on startup, saved after each response
- Cleared on exit (`q`, `quit`, `exit`)
- Format: `[{"type": "human"/"ai", "data": {"content": "..."}}]`

### Message Classes

- `HumanMessage` - user input
- `AIMessage` - model response
- `SystemMessage` - system prompt

## Chat Client

**File**: `app.py`

### Components

- `MCPAgentModule` - main class managing agent, tools, history
- `_load_history()` - loads chat history from JSON
- `_save_history()` - saves to JSON (max 30 messages)
- `_clear_history()` - deletes history on exit
- `invoke_agent()` - non-streaming agent invocation
- `agent_stream()` - streaming agent invocation with reasoning

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MODEL_PROVIDER` | Yes | openai/google/openrouter/groq |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `GOOGLE_API_KEY` | If using Google | Google AI API key |
| `OPEN_ROUTER_API_KEY` | If using OpenRouter | OpenRouter API key |
| `GROQ_API_KEY` | If using Groq | Groq API key |
| `MODEL_TEMPERATURE` | No | Default: 0.5 |
| `MAX_TOKENS` | No | Default: 1500 |
| `DEFAULT_MCP_SERVER_URL` | No | Default SQLite server URL |
| `SQLITE_MCP_DB_PATH` | No | Default: ./datastore/sqlite_ops.db |
| `FASTMCP_HOST` | No | Default: 0.0.0.0 |
| `FASTMCP_PORT` | No | Default: 8000 |
| `FASTMCP2_PORT` | No | Default: 8005 |

## Running the Project

### Docker (Recommended)

```bash
docker compose up
```

Then in another terminal:

```bash
uv run app.py
```

### Manual

```bash
# Terminal 1
uv run --frozen mcps.mcp_server

# Terminal 2
uv run --frozen mcps.mcp_server2

# Terminal 3
uv run app.py
```

## Code Style

- Use type hints where possible
- Prefer async/await for I/O operations
- Use dataclasses for structured data
- Follow existing naming conventions
- Add docstrings to new functions

## Future Enhancements

When expanding this codebase, consider:
- Web UI (FastAPI/Streamlit)
- Interactive MCP server discovery
- Vector store for long-term memory
- Tool result caching
- Request/response validation
- Rate limiting and retries