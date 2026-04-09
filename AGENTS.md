# AGENTS.md - AI Agent Guidelines

This document provides context for AI agents working on this codebase.

## Project Overview

**Project Name**: sqlite-mcp  
**Type**: CLI tool / MCP server  
**Core Functionality**: Natural language interface for SQLite databases using MCP protocol and LangChain agents  
**Status**: Work-in-progress, unstable

## Architecture

The project consists of two main components:

1. **mcp_server.py** (FastMCP server)
   - Runs on http://127.0.0.1:8000/mcp by default
   - Exposes SQLite operations as MCP tools
   - Uses SQLiteUtils from modules/sqlite3/sqlite_1.py
   - Handles database connections, CRUD operations

2. **app.py** (Chat client)
   - Connects to MCP server via langchain_mcp_adapters
   - Uses LangChain create_agent with GPT-4o
   - Provides CLI chat interface with history
   - Translates natural language to SQL operations

## Database Utility

**File**: `modules/sqlite3/sqlite_1.py`  
**Class**: `SQLiteUtils`

### Key Methods

- `create_table(table_name, columns, if_not_exists, primary_key, unique)`
- `insert(table_name, data)` - accepts dict or list[dict]
- `select(table_name, columns, where, order_by, limit, offset, distinct)`
- `update(table_name, data, where)`
- `delete(table_name, where)`
- `upsert(table_name, data, conflict_columns, update_columns)`
- `count(table_name, where)`
- `list_tables()`
- `get_table_info(table_name)`

### Where Clause Builder

The `_build_where_clause` method supports comparison operators via suffixes:
- `__gt` → `>`
- `__lt` → `<`
- `__gte` → `>=`
- `__lte` → `<=`
- `__ne` → `!=`

Example: `{"age__lt": 30, "name__ne": "John"}` becomes `WHERE age < 30 AND name != 'John'`

## MCP Server Tools

All tools are defined in mcp_server.py with FastMCP decorators. Each tool:
- Has async implementation
- Returns dict with "ok" status
- Logs errors instead of raising
- Includes error handling that returns error messages

Current tools:
- list_tables
- table_info  
- create_table
- insert_rows
- select_rows
- select_one_row
- update_rows
- delete_rows
- upsert_row
- count_rows
- active_database

## Chat Client

**File**: app.py

### Components

- `SystemMessage` - defines agent behavior and capabilities
- `create_agent()` - LangChain agent with tools
- `deque` with maxlen=10 - stores chat history

### System Prompt Guidelines

The agent must:
1. Extract column names from natural language
2. Infer SQL types (TEXT, INTEGER, REAL, BLOB)
3. Format as dict: {"column_name": "TYPE"}
4. Handle comparison operators with __gt, __lt, __gte, __lte, __ne suffixes
5. Return meaningful responses to users

### Known Workarounds

1. **columns parameter**: The LLM often fails to include the required `columns` dict when calling create_table. Always ensure columns are provided.

2. **where parameter**: Some operations need explicit where clauses. Use comparison suffixes for non-equality comparisons.

3. **Type inference**: May be inaccurate - column names like "price" should be REAL, "count" should be INTEGER.

## Environment Variables

- `OPENAI_API_KEY` - Required for GPT-4o
- `MCP_SERVER_URL` - MCP server endpoint (default: http://127.0.0.1:8000/mcp)
- `SQLITE_MCP_DB_PATH` - Database file path
- `FASTMCP_HOST` - Server host
- `FASTMCP_PORT` - Server port

## Running the Project

```bash
# Terminal 1: Start MCP server
uv run mcp_server.py

# Terminal 2: Start chat client  
uv run app.py
```

## Testing Queries

```
"create a table named users with columns name age email"
"insert into users name Alice age 25 email alice@example.com"  
"show all users"
"delete users where age < 18"
"update users set age = 26 where name = Alice"
```

## Future Enhancements (For Reference)

When expanding this codebase, consider:
- Add support for MySQL, PostgreSQL, MongoDB, Redis backends
- Support multiple LLM providers (Claude, Gemini, Ollama)
- Implement persistent chat storage (file, database, or vector store)
- Add web interface (Streamlit, FastAPI)
- Implement proper error handling and retry logic
- Add authentication/authorization
- Support for complex queries (JOINs, subqueries)
- Add query optimization suggestions

## Code Style

- Use type hints where possible
- Prefer async/await for I/O operations
- Use dataclasses for structured data
- Follow existing naming conventions
- Add docstrings to new functions
