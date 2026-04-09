# AGENTS.md - AI Agent Guidelines

This document provides context for AI agents working on this codebase.

## Project Overview

**Project Name**: MCP Hub  
**Type**: CLI tool / MCP client  
**Core Functionality**: Universal MCP server connector with LLM-powered chat interface  
**Status**: Work-in-progress

## Architecture

MCP Hub connects to multiple MCP servers and exposes their tools via LangChain agents:

```
app.py (Chat CLI)
       │
       ├── MultiServerMCPClient → MCP Servers (from mcps.py)
       │
       └── create_agent → LLM (OpenAI/Google/Groq/OpenRouter)
```

### Key Files

| File | Purpose |
|------|---------|
| `app.py` | Main chat CLI with history management |
| `modules/mcps.py` | MCP server configurations |
| `modules/agent_utils.py` | LLM factory for multiple providers |
| `modules/logger.py` | Logging setup |
| `modules/system_prompts/` | Agent system prompts |

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

### 3. STDIO with arguments
```python
"server-name": {
    "command": "uvx",
    "transport": "stdio",
    "args": ["@modelcontextprotocol/server-filesystem", "/path"],
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

## Chat History

**File**: `app.py`

- Stored in `chat_history.json` (JSON format)
- Keeps last 20 messages
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
- `_save_history()` - saves to JSON (max 20 messages)
- `_clear_history()` - deletes history on exit
- `invoke_agent()` - non-streaming agent invocation
- `agent_stream()` - streaming agent invocation

### System Prompt

Located in `modules/system_prompts/local_mcp_sqlit3_prompt.py` (SQLite-specific, can be expanded).

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

## Running the Project

```bash
# Start the chat interface
uv run app.py
```

## Future Enhancements

When expanding this codebase, consider:
- Web UI (FastAPI/Streamlit)
- Interactive MCP server discovery
- Vector store for long-term memory
- Tool result caching
- Request/response validation
- Rate limiting and retries

## Code Style

- Use type hints where possible
- Prefer async/await for I/O operations
- Use dataclasses for structured data
- Follow existing naming conventions
- Add docstrings to new functions