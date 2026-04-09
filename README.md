# SQLite-MCP

> **⚠️ WORK IN PROGRESS - UNSTABLE**  
> This project is a proof-of-concept and is currently unstable. Many features require workarounds and the codebase may change significantly.
> 
> **⚠️ WARNING: VIBE CODED - UNTESTED**  
> This project was built to explore LLM capabilities with databases. Most features are **untested** and may break or cause **data loss**. 
> 
> **You use this project at your own risk. I am not responsible for any data loss, damages, or harms caused by using this software.**
> 
> This project is for **exploration and experimentation only**. Do NOT use in production or with important data.

A natural language interface for SQLite databases using MCP (Model Context Protocol) and LangChain AI agents.

## What is This?

SQLite-MCP is a CLI tool that allows you to interact with SQLite databases using natural language. It combines:

- **FastMCP Server**: Exposes SQLite CRUD operations as MCP tools
- **LangChain Agent**: AI-powered chat interface that translates natural language to SQL

## Architecture

```
┌─────────────────┐      MCP/HTTP       ┌──────────────────┐
│   app.py        │ ◄─────────────────► │  mcp_server.py   │
│ (Chat Client)   │                     │  (FastMCP)       │
└────────┬────────┘                     └────────┬─────────┘
         │                                         │
         │ LangChain Agent                        │
         │ (GPT-4o)                               │ SQLiteUtils
         │                                        │ (sqlite_1.py)
         │                                        ▼
         │                                 ┌──────────────┐
         │                                 │  SQLite DB   │
         │                                 └──────────────┘
         ▼
    User Terminal
```

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key

### Installation

```bash
# Clone the repository
cd sqlite-mcp

# Install dependencies
uv pip install -r requirements.txt
or
uv sync
```

### Configuration

Create a `.env` file:

```bash
# Required: Your OpenAI API key
OPENAI_API_KEY=sk-your-key-here

# Optional: Custom server URL (default: http://127.0.0.1:8000/mcp)
MCP_SERVER_URL=http://127.0.0.1:8000/mcp

# Optional: Database path (default: ./sqlite_ops.db)
SQLITE_MCP_DB_PATH=./sqlite_ops.db
```

### Running

**Terminal 1 - Start MCP Server:**

```bash
uv run mcp_server.py
```

**Terminal 2 - Start Chat Client:**

```bash
uv run app.py
```

### Usage

```
Connecting to http://127.0.0.1:8000/mcp...
✅ MCP server connected! Tools loaded: ['list_tables', 'table_info', 'create_table', 'insert_rows', 'select_rows', 'select_one_row', 'update_rows', 'delete_rows', 'upsert_row', 'count_rows', 'active_database']
Loaded 11 tools.
Enter your query: create a table named users with columns name age email
Enter your query: insert into users name Alice age 25 email alice@example.com
Enter your query: show all users
Enter your query: delete all users where age < 18
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in the database |
| `table_info` | Get schema information for a table |
| `create_table` | Create a new table |
| `insert_rows` | Insert one or more rows |
| `select_rows` | Query rows with filters |
| `select_one_row` | Query a single row |
| `update_rows` | Update existing rows |
| `delete_rows` | Delete rows |
| `upsert_row` | Insert or update on conflict |
| `count_rows` | Count rows |
| `active_database` | Get current database path |

## Known Issues & Workarounds

1. **Missing `columns` parameter**: When creating tables, the LLM may forget to include the required `columns` dict. System prompt includes guidance for this.

2. **Comparison operators**: Natural language like "age below 30" needs special handling. Use `__gt`, `__lt`, `__gte`, `__lte`, `__ne` suffixes:
   - `"age < 30"` → `{"age__lt": 30}`
   - `"age >= 25"` → `{"age__gte": 25}`

3. **Type inference**: The LLM must infer SQL types (TEXT, INTEGER, REAL) from column names. This may not always be accurate.

## Project Structure

```
sqlite-mcp/
├── app.py              # Chat client with LangChain agent
├── mcp_server.py       # FastMCP server exposing SQLite tools
├── modules/
│   └── sqlite3/
│       ├── sqlite_1.py # SQLiteUtils wrapper class
│       ├── sqlite_2.py # (unused)
│       └── sqlite_3.py # (unused)
├── sqlite_ops.db       # Default SQLite database
├── pyproject.toml     # Project configuration
└── .env              # Environment variables
```

## Requirements

```
fastmcp>=2.0
langchain>=0.3
langchain-openai>=0.2
langgraph>=0.2
langchain-mcp-adapters>=0.1
python-dotenv
loguru
```

## Future Features (Planned)

- [ ] **Multi-database support**: MySQL, PostgreSQL, MongoDB, Redis
- [ ] **Multi-model support**: Claude, Gemini, local models (Ollama)
- [ ] **Persistent chat storage**: Save conversation history
- [ ] **Web UI**: Browser-based interface
- [ ] **Batch operations**: Execute multiple queries at once
- [ ] **Query optimization hints**: LLM suggests indexes
- [ ] **Data export**: Export results as CSV, JSON, Excel
- [ ] **Schema migration tools**: Version control for database schemas
- [ ] **RBAC**: Role-based access control
- [ ] **API server**: RESTful API for remote access

## Limitations

- Only supports SQLite (for now)
- Requires OpenAI API key (for now)
- No persistent chat history between sessions
- Type inference can be unreliable
- Limited error handling - may crash on edge cases
- No authentication on MCP server

## Contributing

This is a work-in-progress project. Contributions welcome but expect rapid changes.

## License

See [LICENSE](LICENSE) for full terms of use. This project is not open source - explicit permission is required for any use beyond personal development and learning.
