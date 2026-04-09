# MCP Hub

> A universal CLI for connecting to multiple MCP servers and interacting with them via natural language using LLMs.

## What is This?

**MCP Hub** is a flexible CLI tool that lets you connect to any MCP (Model Context Protocol) server—whether running locally or via `uvx`—and interact with them through an AI-powered chat interface. It supports multiple LLM providers (OpenAI, Google, OpenRouter, Groq) and maintains chat history.

## Features

- **Multi-Server Support**: Connect to any number of MCP servers (local or uvx-based)
- **Multi-Model Support**: Use GPT, Gemini, Groq, or OpenRouter models
- **Chat History**: Persistent JSON-based conversation history (last 20 messages)
- **Universal Tools**: Any MCP tools exposed by connected servers are automatically available

## Architecture

```
┌─────────────┐      LangChain Agent       ┌─────────────────────┐
│  app.py     │ ◄─────────────────────────►│  MCP Servers        │
│ (Chat CLI)  │                            │  (via mcps.py config)│
└─────────────┘                            └─────────────────────┘
       │                                            │
       │  Multiple LLM Providers                   │
       │  (OpenAI/Google/Groq/OpenRouter)          │
       ▼                                            ▼
   User Terminal                            Your Tools/APIs
```

## Quick Start

### Prerequisites

- Python 3.11+
- API keys for your chosen LLM provider(s)

### Installation

```bash
# Install dependencies
uv sync
# or
uv pip install -r requirements.txt
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

# Model name (optional - can be set per provider)
OPENAI_MODEL=gpt-4o
GOOGLE_MODEL=gemini-2.0-flash
OPEN_ROUTER_MODEL=x-ai/grok-4.1-fast
GROQ_MODEL=llama-3.3-70b-versatile

# Optional settings
MODEL_TEMPERATURE=0.5
MAX_TOKENS=1500

# Optional: Custom MCP servers (see mcps.py)
# MCP_SERVER_URL=http://127.0.0.1:8000/mcp
```

### Adding MCP Servers

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
    # Another uvx server
    "filesystem": {
        "command": "uvx",
        "transport": "stdio",
        "args": ["@modelcontextprotocol/server-filesystem", "/path/to/folder"],
    },
}
```

### Running

```bash
uv run app.py
```

### Usage

```
Enter Your Query: search for python tutorials
Enter Your Query: show my files in /docs
Enter Your Query: list tables in my database
Enter Your Query: q
```

## Project Structure

```
mcp-hub/
├── app.py                      # Main chat CLI
├── mcp_server.py               # (Legacy) SQLite MCP server
├── modules/
│   ├── __init__.py             # Exports
│   ├── agent_utils.py          # LLM factory (OpenAI/Google/Groq/OpenRouter)
│   ├── mcps.py                 # MCP server configurations
│   ├── logger.py               # Logging setup
│   ├── sqlite3/                # SQLite utilities
│   └── system_prompts/         # System prompts for agents
├── chat_history.json           # Chat history (auto-generated)
└── .env                        # Environment variables
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
- Keeps last 20 messages
- Automatically cleared on exit
- Contains only message content (no metadata)

## Roadmap

- [ ] Web UI (FastAPI/Streamlit)
- [ ] SQLite operations via built-in MCP
- [ ] File-based MCP server starter
- [ ] Interactive MCP server management
- [ ] Vector store for long-term memory
- [ ] Multi-turn tool orchestration

## Requirements

```
langchain>=0.3
langchain-openai
langchain-google-genai
langchain-openrouter
langchain-groq
langchain-mcp-adapters
fastmcp
python-dotenv
loguru
```

## License

MIT