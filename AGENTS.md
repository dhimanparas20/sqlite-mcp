# AGENTS.md — AI Agent Operating Manual

> **This file is written FOR AI/LLM agents.** Read it carefully to understand how to operate this system effectively.

---

## 1. Executive Summary

You are operating **MCP Hub**, an AI agent platform that gives LLMs real-world capabilities through:

- **MCP Servers** (FastMCP-based): SQLite, Filesystem, Downloader, Web Search, Web Fetch, Time, PageIndex
- **LangChain Tools**: Background task queuing (Huey), email, weather, file management, scheduling
- **Embedding & Vector Search**: ChromaDB-powered semantic search over files and URLs
- **Multi-Provider LLM Support**: OpenAI, Google Gemini, Groq, OpenRouter, NVIDIA
- **Multi-Provider Embedding Support**: OpenAI, Google, OpenRouter, NVIDIA

**Your job**: Understand user intent, select the right tool(s), execute them in the correct order, and respond helpfully.

---

## 2. System Architecture

### 2.1 Request Flow

```
User Input
    |
    v
FastAPI (app.py) ──lifespan──> MCPAgentModule.init()
    |                                   |
    v                                   v
/api/chat POST              [System Prompt + History]
    |                                   |
    v                                   v
agent.invoke_agent()        LLM + All Tools
    |                                   |
    +<── Tool Call Results ────────────+
    |
    v
ChatResponse (JSON)
```

### 2.2 Module Responsibility Map

| File | Role | What You Need to Know |
|------|------|----------------------|
| `app.py` | FastAPI app | Handles HTTP lifecycle, chat API, history management. Initializes `MCPAgentModule` on startup. |
| `modules/agent_mod.py` | Agent orchestrator | `MCPAgentModule` class. Loads MCP tools, LangChain tools, LLM, system prompt, and chat history. `invoke_agent()` is the main entry point. |
| `modules/agent_utils.py` | LLM factory | `create_llm()` dynamically imports the correct LangChain chat model class based on `MODEL_PROVIDER` env var. Registry: openai → ChatOpenAI, google → ChatGoogleGenerativeAI, openrouter → ChatOpenRouter, groq → ChatGroq, nvidia → ChatNVIDIA. |
| `modules/embedder.py` | Embedding & ChromaDB | `create_embeddings()` factory (mirrors `create_llm`), `embed_and_store()` pipeline, `query_documents()` search, `list_collections()`, `clear_collection()`, `delete_collection()`. Supports PDF, MD, CSV, TXT, JSON, DOCX, HTML, XML, and web URLs. |
| `modules/tools/__init__.py` | Tool registry | Re-exports all tools from submodules. Contains `get_vectorless_tools()` which returns the full tool list for the agent. |
| `modules/tools/background.py` | Background task tools | `index_files`, `index_urls`, `send_email_task`, `schedule_task`, `sleep`, `get_background_task_status`, `get_all_tasks`. All return job IDs. |
| `modules/tools/datetime.py` | DateTime tool | `get_system_datetime` — MUST use for all time-based calculations. |
| `modules/tools/embedding.py` | ChromaDB tools | `embed_file`, `query_embedded_data`, `list_chroma_collections`, `clear_chroma_collection`, `delete_chroma_collection`. |
| `modules/tools/file_management.py` | File ops | `FileManagementToolkit` tools (read, write, copy, move, delete, list, make, move_dir). Sandboxed to `DATASTORE_DIR`. |
| `modules/tools/weather.py` | Weather tool | `weather_tool` via OpenWeatherMap. |
| `tasks/tasks.py` | Huey tasks | `index_documents_task`, `send_email_task`, `test_sleep_task`, `test_schedule_task`. `schedule_task()` is the generic scheduler. `get_job_status()` checks task status. |
| `mcps/__init__.py` | MCP registry | `MCP_TOOLS` dict configures all MCP servers with transport type (stdio or streamable-http), URLs, commands, and env vars. |
| `mcps/mcp_sql.py` | SQLite MCP server | FastMCP server exposing SQLite CRUD operations. Runs on port 8000. Uses `SQLiteUtils` from `modules/sqlite3/sqlite_1.py`. |
| `mcps/mcp_fs.py` | Filesystem MCP server | FastMCP server for file operations. Runs on port 8005. **Currently NOT registered in `MCP_TOOLS`** — file ops come from `FileManagementToolkit` in `modules/tools/file_management.py`. |
| `mcps/mcp_downloader.py` | Downloader MCP server | FastMCP server for URL downloads with progress tracking. Runs on port 8010. |
| `modules/system_prompts/general_prompt.py` | Main system prompt | Injected as the first message on every request. Describes all tools, critical rules, and usage examples. `{MY_EMAIL}` is substituted from env. |
| `modules/system_prompts/local_mcp_sqlit3_prompt.py` | SQLite prompt | Specialized prompt for pure SQLite interactions (not the main agent prompt). |
| `modules/logger.py` | Logging | Colorized logger with PID support. Use `get_logger(name)` for consistent logging. |
| `modules/sqlite3/sqlite_1.py` | SQLiteUtils | Production SQLite wrapper used by `mcp_sql.py`. Dict-based CRUD, upsert, transactions, raw queries, backups. |
| `modules/sqlite3/sqlite_2.py` | SQLiteManager | Alternative SQLite wrapper with WAL mode, pagination, search. |
| `modules/sqlite3/sqlite_3.py` | SQLiteDB | Modern SQLite wrapper with savepoint-based nested transactions, identifier quoting, JSON serialization. |

---

## 3. How the Agent Decides Tools

### 3.1 Tool Loading Sequence

During `MCPAgentModule.init()`:

1. `MultiServerMCPClient(MCP_TOOLS)` connects to all configured MCP servers
2. `get_tools()` fetches MCP tool schemas dynamically
3. `get_vectorless_tools()` loads LangChain tools from `modules/tools/__init__.py`
4. `all_tools = mcp_tools + vectorless_tools`
5. `create_agent(model=llm, tools=all_tools)` creates the LangChain agent

### 3.2 Tool Categories

When reasoning about which tool to use, categorize the user request:

| User Wants To... | Tool Category | Examples |
|------------------|---------------|----------|
| Query/create/update/delete database data | **MCP: sqlite-local** | `create_table`, `insert_rows`, `select_rows`, `execute_sql` |
| Download a file from URL | **MCP: downloader** | `download_file`, `download_batch` |
| Search the internet | **MCP: ddg-search** | Web search tool |
| Read a webpage | **MCP: fetch** | Page content extraction |
| Get time in a timezone | **MCP: time** | Time lookup |
| Query indexed documents | **MCP: pageindex** | Semantic search over PDFs/notes |
| Index files for AI search | **LangChain: index_files** | Queues `index_documents_task` |
| Index URLs for AI search | **LangChain: index_urls** | Queues `index_documents_task` |
| **Embed a file/URL locally** | **LangChain: embed_file** | **Embeds to ChromaDB for local semantic search** |
| **Search embedded content** | **LangChain: query_embedded_data** | **Semantic search over ChromaDB** |
| **Manage vector collections** | **LangChain: chroma tools** | **list, clear, delete collections** |
| Send an email | **LangChain: send_email_task** | Queues `send_email_task` |
| Schedule a future task | **LangChain: schedule_task** | Generic Huey scheduler |
| Check if a task is done | **LangChain: get_background_task_status** | Job status lookup |
| Get current time | **LangChain: get_system_datetime** | System time (MUST use for scheduling) |
| Get weather | **LangChain: weather_tool** | Weather lookup |
| Read/write/copy/move/delete files | **LangChain: file_management** | FileManagementToolkit tools |

### 3.3 Multi-Step Reasoning

Complex requests require multiple tool calls in sequence:

**Example: "Send me a summary of today's AI news via email in 5 minutes"**

1. `get_system_datetime_tool()` → get current time
2. `ddg-search` → search for "AI news today"
3. `fetch` → read top result pages for detail
4. `schedule_task_tool(task_name="send_email_task", delay=300, task_kwargs={to: MY_EMAIL, subject: "AI News Summary", body: summary})`

**Example: "Create a todos table and add 'Buy groceries'"**

1. `sqlite-local.create_table` → create `todos` table
2. `sqlite-local.insert_rows` → insert the todo item

**Example: "Embed this PDF and tell me what it says about revenue"**

1. `embed_file_tool(source="./datastore/docs/report.pdf", collection_name="reports")` → embed the file
2. `query_embedded_data_tool(query="revenue", collection_name="reports", k=5)` → search for relevant chunks
3. Synthesize the results into a clear answer

**Example: "Embed this webpage and summarize it"**

1. `embed_file_tool(source="https://example.com/article", collection_name="web")` → embed the URL
2. `query_embedded_data_tool(query="summary of the article", collection_name="web", k=10)` → get chunks
3. Synthesize findings into a summary

---

## 4. MCP Server Catalog

### 4.1 sqlite-local (Port 8000, streamable-http)

**Connection:** `http://mcp_sql:8000/mcp/`

**Tools available:**

| Tool Name | Parameters | Returns |
|-----------|------------|---------|
| `list_tables` | — | `list[str]` |
| `table_info` | `table_name: str` | `dict` with columns schema or `None` |
| `create_table` | `table_name`, `columns` (dict or list), `if_not_exists=True`, `primary_key=None`, `unique=None` | `{"ok": bool, "table": str, "error?": str}` |
| `insert_rows` | `data: dict/list[dict]`, `table_name: str` | `{"rows_inserted": int, "row_id?": int, "row_ids?": list}` |
| `select_rows` | `table_name`, `columns=None`, `where=None`, `order_by=None`, `limit=None`, `offset=None`, `distinct=False` | `list[dict]` |
| `select_one_row` | `table_name`, `columns=None`, `where=None`, `order_by=None` | `dict` or `None` |
| `update_rows` | `table_name`, `data: dict`, `where=None` | `{"ok": bool, "rows_updated": int}` |
| `delete_rows` | `table_name`, `where=None` | `{"ok": bool, "rows_deleted": int}` |
| `upsert_row` | `table_name`, `data: dict`, `conflict_columns: list`, `update_columns=None` | `{"ok": bool, "rows_affected": int}` |
| `count_rows` | `table_name`, `where=None` | `{"count": int}` |
| `execute_sql` | `sql: str`, `params=None` | `{"ok": bool, "columns?": list, "rows?": list, "row_count?": int, "affected_rows?": int, "error?": str}` |
| `create_index` | `index_name`, `table_name`, `columns: list`, `unique=False`, `if_not_exists=True` | `{"ok": bool, ...}` |
| `list_indexes` | — | `{"ok": bool, "indexes": list, "count": int}` |
| `delete_table` | `table_name: str` | `{"ok": bool, ...}` |
| `rename_table` | `table_name`, `new_table_name` | `{"ok": bool, ...}` |
| `flush_database` | — | `{"ok": bool, "tables_dropped": list, "count": int}` |
| `vacuum_database` | — | `{"ok": bool}` |
| `active_database` | — | `{"db_path": str}` |

**SQLite Comparison Operators in WHERE clauses:**
Use suffix notation for comparisons:
- `age__gt`: greater than (`>`)
- `age__lt`: less than (`<`)
- `age__gte`: greater than or equal (`>=`)
- `age__lte`: less than or equal (`<=`)
- `age__ne`: not equal (`!=`)

### 4.2 downloader (Port 8010, streamable-http)

**Connection:** `http://mcp_downloader:8010/mcp`

| Tool Name | Parameters | Returns |
|-----------|------------|---------|
| `download_file` | `url: str`, `custom_filename=None`, `timeout=300` | `{"ok": bool, "filename": str, "path": str, "size_bytes": int, ...}` |
| `download_batch` | `urls: list[str]`, `timeout=300`, `stop_on_error=False` | `{"ok": bool, "total": int, "successful": int, "failed": int, "results": list}` |
| `list_downloads` | — | `{"ok": bool, "files": list, "count": int}` |
| `get_download_info` | `filename: str` | `{"ok": bool, "name": str, "path": str, "size_bytes": int, ...}` |
| `delete_download` | `filename: str` | `{"ok": bool}` |
| `delete_all_downloads` | — | `{"ok": bool, "deleted": list, "count": int}` |
| `get_download_dir` | — | `{"ok": bool, "path": str, "total_size_bytes": int, "file_count": int}` |
| `check_url` | `url: str`, `timeout=10` | `{"ok": bool, "status_code": int, "content_length": str, "content_type": str, ...}` |

### 4.3 ddg-search (stdio)

**Command:** `uv run duckduckgo-mcp-server`

**Environment:**
- `DDG_SAFE_SEARCH=MODERATE`
- `DDG_REGION=in-en`

Returns web search results with titles, URLs, and snippets.

### 4.4 fetch (stdio)

**Command:** `uv run mcp-server-fetch`

Fetches webpage content and returns extracted text. Good for reading articles, documentation, etc.

### 4.5 time (stdio)

**Command:** `uv run mcp-server-time`

Returns current time for specified timezones.

### 4.6 pageindex (HTTP)

**URL:** `https://api.pageindex.ai/mcp`

**Headers:** `Authorization: Bearer {PAGE_INDEX_API_KEY}`

Allows querying documents that have been indexed via `index_files` or `index_urls` tools.

### 4.7 url-downloader (stdio)

**Command:** `uv run mcp-url-downloader --path /home/paras/Downloads/mcp_downloads`

Alternative downloader with a fixed output directory.

---

## 5. LangChain Tool Catalog

Tools are organized in `modules/tools/` by category. All are re-exported via `modules/tools/__init__.py`.

### 5.1 Background Task Tools (`modules/tools/background.py`)

These tools queue work and return immediately. **Always share the job ID with the user.**

**`index_files_tool(file_paths: str | list[str])`**
- Queues `index_documents_task(sources=file_paths)`
- Returns: `{"success": true, "id": "job-id"}`

**`index_urls_tool(urls: str | list[str])`**
- Queues `index_documents_task(sources=urls)`
- Downloads remote files first, then indexes them
- Returns: `{"success": true, "id": "job-id"}`

**`send_email_task_tool(to: str | list[str], subject: str, body: str, is_html=False)`**
- Queues `send_email_task(to=to, subject=subject, body=body, is_html=is_html)`
- Uses Gmail SMTP (`smtp.gmail.com:587`)
- Requires `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` env vars
- Returns: `{"success": true, "id": "job-id"}`

**`schedule_task_tool(task_name: str, task_args=None, task_kwargs=None, delay=None, eta=None)`**
- Generic scheduler for any Huey task
- Available tasks: `test_sleep_task`, `test_schedule_task`, `send_email_task`, `index_documents_task`
- `delay`: seconds from now
- `eta`: ISO8601 datetime string (e.g., `"2026-04-15T09:00:00"`)
- Returns: `{"success": true, "id": "job-id", "task": "task_name"}`

**`sleep_tool(sleep_time: int = 5)`**
- Queues `test_sleep_task(sleep_time=sleep_time)`
- For testing background task system
- Returns: `{"success": true, "id": "job-id"}`

**`get_background_task_status_tool(job_id: str)`**
- Checks Huey result storage
- Returns: `{"status": "pending" | "finished" | "not_found", "result": any}`

**`get_all_tasks_tool()`**
- Lists scheduled and pending tasks in Huey queue
- Returns: `{"scheduled": [...], "pending": [...]}`

### 5.2 DateTime Tool (`modules/tools/datetime.py`)

**`get_system_datetime_tool()`**
- Returns current system time
- **CRITICAL**: Must use this for ALL time-based calculations
- Returns: `{"datetime": "2026-04-10 23:00:00", "iso": "...", "timestamp": int, "timezone": "..."}`

### 5.3 Embedding & Vector Store Tools (`modules/tools/embedding.py`)

These tools interact with the local ChromaDB vector store for semantic search over files and URLs.

**`embed_file_tool(source: str, collection_name: str = "default")`**
- Embeds a file or URL into ChromaDB
- Supported formats: PDF, MD, CSV, TXT, JSON, DOCX, HTML, XML, web URLs
- Pipeline: Load → Chunk (1000 chars, 200 overlap) → Embed → Store
- Returns: `{"ok": true, "chunks": int, "collection": str, "persist_dir": str}`

**`query_embedded_data_tool(query: str, collection_name: str = "default", k: int = 4)`**
- Semantic search over embedded documents
- Returns top-k matching chunks with content and metadata
- Returns: `{"ok": true, "query": str, "collection": str, "results": [{"content": str, "metadata": dict}]}`

**`list_chroma_collections_tool()`**
- Lists all ChromaDB collections with document counts
- Returns: `{"ok": true, "collections": [{"name": str, "count": int}], "count": int}`

**`clear_chroma_collection_tool(collection_name: str = "default")`**
- Deletes all documents from a collection (keeps the collection)
- Returns: `{"ok": true, "collection": str, "deleted": int}`

**`delete_chroma_collection_tool(collection_name: str = "default")`**
- Permanently deletes an entire collection and all its data
- Returns: `{"ok": true, "collection": str, "deleted": true}`

### 5.4 Weather Tool (`modules/tools/weather.py`)

**`weather_tool`**
- LangChain community tool using OpenWeatherMap
- Requires `OPENWEATHERMAP_API_KEY` env var
- Query format: `"What's the weather in Tokyo?"`

### 5.5 File Management Tools (`modules/tools/file_management.py`)

From `FileManagementToolkit(root_dir=os.getenv("DATASTORE_DIR"))`:

- `read_file` — Read file contents
- `write_file` — Write content to file
- `copy_file` — Copy files
- `move_file` — Move/rename files
- `delete_file` — Delete files
- `list_directory` — List directory contents
- `make_directory` — Create directories
- `move_directory` — Move directories

**Important:** These operate within `DATASTORE_DIR` only.

---

## 6. Embedding System (`modules/embedder.py`)

### 6.1 Embedding Provider Registry

Mirrors the `create_llm()` pattern from `agent_utils.py`. The `EMBEDDING_REGISTRY` maps provider names to their LangChain class configurations:

| Provider | Class | Module | Model Env Var | API Key Env Var |
|----------|-------|--------|--------------|-----------------|
| `openai` | `OpenAIEmbeddings` | `langchain_openai` | `OPENAI_EMBEDDINGS_MODEL` | `OPENAI_API_KEY` |
| `google` | `GoogleGenerativeAIEmbeddings` | `langchain_google_genai` | `GOOGLE_EMBEDDINGS_MODEL` | `GOOGLE_API_KEY` |
| `openrouter` | `OpenAIEmbeddings` | `langchain_openai` | `OPEN_ROUTER_EMBEDDINGS_MODEL` | `OPEN_ROUTER_API_KEY` |
| `nvidia` | `NVIDIAEmbeddings` | `langchain_nvidia_ai_endpoints` | `NVIDIA_EMBEDDINGS_MODEL` | `NVIDIA_API_KEY` |

**`create_embeddings(model_name=None, api_key=None, provider="openai")`**
- Factory function that returns a LangChain embeddings instance
- Falls back to env vars for model name and API key
- Uses `EMBEDDING_PROVIDER` env var if provider not specified

### 6.2 Document Loaders

`load_documents(source: str | list[str])` auto-detects file type and uses the appropriate loader:

| Extension | Loader |
|-----------|--------|
| `.pdf` | `PyPDFLoader` |
| `.md`, `.markdown` | `UnstructuredMarkdownLoader` |
| `.csv` | `CSVLoader` |
| `.txt` | `TextLoader` |
| `.json` | `JSONLoader` |
| `.docx`, `.doc` | `Docx2txtLoader` |
| `.html`, `.htm` | `UnstructuredHTMLLoader` |
| `.xml` | `UnstructuredXMLLoader` |
| `http://...`, `https://...` | `WebBaseLoader` |
| Other | Falls back to `TextLoader` |

### 6.3 ChromaDB Storage

- Persisted at `CHROMA_DIR` (default: `./datastore/internal/chroma/`)
- Uses `langchain-chroma` for LangChain integration
- Collections are created automatically on first embed
- Data survives container restarts

---

## 7. Critical Rules

### 7.1 Time-Based Operations

**FOR ANY TIME-BASED ACTIVITY** (scheduling tasks, calculating delays, etc.):

1. **ALWAYS** call `get_system_datetime_tool()` first
2. Use that time to calculate durations or future timestamps
3. **NEVER** assume or hardcode times

**Correct workflow:**
```
User: "Send email in 3 minutes"
→ get_system_datetime_tool() → "2026-04-10 22:54:00"
→ Calculate: 22:54:00 + 3 min = 22:57:00
→ schedule_task_tool(task_name="send_email_task", delay=180, task_kwargs={...})
→ Tell user: "Email scheduled for 22:57:00, Job ID: abc-123"
```

### 7.2 Background Tasks & Job IDs

Tools like `index_files`, `index_urls`, `send_email_task`, `schedule_task`, `sleep` are **ASYNCHRONOUS**:

- They return **IMMEDIATELY** with a job ID
- Actual work happens in the background (can take seconds to minutes)
- **ALWAYS** share the job ID with the user
- Use `get_background_task_status` with the job ID to check completion

### 7.3 File Operations

- All file creation/imports should check `./datastore` directory first
- Downloaded files go to `./datastore/downloads`
- Use `file_management` tools or `downloader` MCP for file operations
- When creating new files, ensure parent directories exist

### 7.4 Notes & Todos Handling

When user asks to make notes or todos:

1. First, query SQLite to check if a related table exists (e.g., `notes`, `todos`, `tasks`)
2. If table exists, use it for operations
3. If no related table exists, tell the user there are no existing notes/todos
4. If user confirms they want to create one, create an appropriate SQLite table with well-suited columns (e.g., `id`, `title`, `description`, `created_at`, `updated_at`, `status`, `priority`)
5. Always inform the user about the table creation and its structure

### 7.5 Database Safety

- Use `execute_sql` for raw queries, but prefer structured tools (`select_rows`, `insert_rows`, etc.) when possible
- `flush_database` drops ALL tables — warn the user before using
- Always check `table_info` before assuming column names

### 7.6 Embedding Workflow

When a user asks to read, analyze, or extract content from a file (PDF, MD, CSV, etc.) or URL:

1. **Embed first**: `embed_file_tool(source="...", collection_name="...")`
2. **Then query**: `query_embedded_data_tool(query="...", collection_name="...", k=5)`
3. Synthesize the returned chunks into a clear answer

**Use `collection_name` to organize embeddings by topic or source** (e.g., "reports", "web-articles", "project-docs").

**ChromaDB management:**
- Use `list_chroma_collections_tool()` to see what's embedded
- Use `clear_chroma_collection_tool()` to empty a collection
- Use `delete_chroma_collection_tool()` to remove a collection entirely

---

## 8. System Prompt Architecture

### 8.1 Main System Prompt

Located in `modules/system_prompts/general_prompt.py`.

**Structure:**
1. **Tool Categories** — Organized by domain (Database, Filesystem, Web, Time, Indexing, Email, Scheduling, Utility, File Management, **Embedding & Vector Store**)
2. **Available Tasks for Scheduling** — Lists Huey tasks that can be scheduled
3. **Critical Rules** — Time rules, background task rules, file operation rules, notes/todos rules, **embedding workflow rules**
4. **Usage Examples** — Concrete multi-step examples including embed→query workflows
5. **Guidelines** — General behavior rules

**Dynamic Substitution:**
- `{MY_EMAIL}` is replaced with the value of `MY_EMAIL` env var at import time

### 8.2 SQLite-Specific Prompt

Located in `modules/system_prompts/local_mcp_sqlit3_prompt.py`.

Used for SQLite-focused interactions. Contains:
- Column type inference rules (TEXT for names, INTEGER for ages, REAL for prices)
- WHERE clause comparison operator syntax (`__gt`, `__lt`, `__gte`, `__lte`, `__ne`)
- Data representation guidelines (tabular form)

---

## 9. Chat History Management

### 9.1 History Files

| File | Purpose | Max Entries |
|------|---------|-------------|
| `datastore/internal/chat_history.json` | Agent's internal conversation history | 30 |
| `datastore/internal/api_chat_history.json` | API-exposed chat history | 30 |

### 9.2 History Format

```json
[
  {"type": "human", "data": {"content": "user message"}},
  {"type": "ai", "data": {"content": "assistant response"}}
]
```

### 9.3 History Lifecycle

- Loaded during `MCPAgentModule.init()` and `invoke_agent()`
- Saved after each successful response
- Automatically trimmed to `MAX_HISTORY` (30) messages
- Cleared on `/api/clear` or application shutdown

---

## 10. Common Agent Patterns

### 10.1 Web Search + Summarize

```
1. ddg-search(query="...")
2. For each interesting result: fetch(url="...")
3. Synthesize findings into a clear answer
```

### 10.2 Database Workflow

```
1. list_tables (check if table exists)
2. table_info (understand schema)
3. Perform CRUD operation
4. Confirm results to user
```

### 10.3 Email Workflow

```
1. If scheduling: get_system_datetime_tool()
2. If recipient is "me"/"my email": use MY_EMAIL env var
3. send_email_task_tool(to=..., subject=..., body=...)
4. Report job ID to user
```

### 10.4 Document Indexing Workflow (PageIndex — Cloud)

```
1. index_files_tool(file_paths=["..."]) OR index_urls_tool(urls=["..."])
2. Report job ID: "Indexing started, Job ID: xyz"
3. User can check: get_background_task_status_tool(job_id="xyz")
4. Once finished, user can query: pageindex tool
```

### 10.5 Document Embedding Workflow (ChromaDB — Local)

```
1. embed_file_tool(source="file.pdf" or "https://...", collection_name="my-docs")
2. Report: "Embedded N chunks into collection 'my-docs'"
3. query_embedded_data_tool(query="what does it say about X?", collection_name="my-docs", k=5)
4. Synthesize returned chunks into a clear answer
```

### 10.6 Task Scheduling Workflow

```
1. get_system_datetime_tool() → get current time
2. Calculate delay or ETA
3. schedule_task_tool(
     task_name="send_email_task",
     task_kwargs={"to": "...", "subject": "...", "body": "..."},
     delay=180
   )
4. Report: "Task scheduled to run at [time], Job ID: xyz"
```

---

## 11. LLM Provider Details

### 11.1 Configuration

Set via environment variables:

| Provider | Model Env Var | API Key Env Var |
|----------|--------------|-----------------|
| OpenAI | `OPENAI_MODEL` | `OPENAI_API_KEY` |
| Google | `GOOGLE_MODEL` | `GOOGLE_API_KEY` |
| Groq | `GROQ_MODEL` | `GROQ_API_KEY` |
| OpenRouter | `OPEN_ROUTER_CHAT_MODEL` | `OPEN_ROUTER_API_KEY` |
| NVIDIA | `NVIDIA_MODEL` | `NVIDIA_API_KEY` |

### 11.2 Embedding Provider Configuration

| Provider | Model Env Var | API Key Env Var |
|----------|--------------|-----------------|
| OpenAI | `OPENAI_EMBEDDINGS_MODEL` | `OPENAI_API_KEY` |
| Google | `GOOGLE_EMBEDDINGS_MODEL` | `GOOGLE_API_KEY` |
| OpenRouter | `OPEN_ROUTER_EMBEDDINGS_MODEL` | `OPEN_ROUTER_API_KEY` |
| NVIDIA | `NVIDIA_EMBEDDINGS_MODEL` | `NVIDIA_API_KEY` |

Set `EMBEDDING_PROVIDER` env var to choose the embedding provider (default: `openai`).

### 11.3 Temperature & Tokens

- `MODEL_TEMPERATURE`: 0.0 = deterministic, 1.0 = creative (default: 0.4)
- `MAX_TOKENS`: Maximum response length (default: 1500)

### 11.4 Fallback Behavior

If `model_name` is not provided to `create_llm()`, it falls back to the provider's env var.
If `api_key` is not provided, it falls back to the provider's env var.
If neither is available, raises `ValueError`.

Same pattern applies to `create_embeddings()`.

---

## 12. Docker Service Interdependencies

```
valkey (no deps)
    |
    +--> huey (depends on valkey)
    |
mcp_sql (no deps)
    |
mcp_downloader (no deps)
    |
    +--> app (depends on mcp_sql, mcp_downloader, huey being healthy)
```

The `app` service waits for `mcp_sql` and `mcp_downloader` health checks before starting.

---

## 13. Debugging Guide for Agents

### 13.1 Agent Not Responding

- Check `/ping` — is the FastAPI app running?
- Check agent initialization logs — did `MCPAgentModule.init()` complete?
- Verify LLM API key is valid and has credits

### 13.2 Tool Call Failing

- Check tool name spelling — MCP tools use kebab-case names in the registry but the actual tool names may differ
- Check parameters — are required params provided?
- For MCP tools: check if the MCP server container is running (`docker compose ps`)
- For background tasks: check Huey worker logs (`docker compose logs huey`)

### 13.3 SQLite Errors

- Check `active_database()` to confirm which DB file is being used
- Use `table_info()` to verify schema before operations
- For `execute_sql`, ensure SQL syntax is valid SQLite
- Check if table exists with `list_tables()` before referencing it

### 13.4 Background Task Never Completes

- Verify `huey` container is running
- Check Redis connectivity: `docker compose exec valkey valkey-cli -a testpass ping`
- Verify `REDIS_URL` env var matches Valkey password
- Check Huey logs for error traces

### 13.5 File Operation Errors

- FileManagementToolkit is restricted to `DATASTORE_DIR`
- Check `list_directory` to verify paths exist
- Use relative paths from `DATASTORE_DIR` root

### 13.6 Embedding / ChromaDB Errors

- ChromaDB data persists at `CHROMA_DIR` (default: `./datastore/internal/chroma/`)
- Deleting this folder resets all embeddings
- Ensure `EMBEDDING_PROVIDER` is set and the corresponding API key is valid
- Use `list_chroma_collections_tool()` to verify collections exist
- Check embedding provider logs for API errors

---

## 14. Adding New Capabilities

### 14.1 Adding an MCP Server

1. Add server config to `mcps/__init__.py` in `MCP_TOOLS`
2. If custom implementation: create `mcps/mcp_<name>.py` with FastMCP instance
3. Add health check endpoint (`@mcp.custom_route("/health")`)
4. Add service to `compose.yml` with proper ports and health checks
5. Update `modules/system_prompts/general_prompt.py` to describe the new tool
6. Restart services: `docker compose up -d`

### 14.2 Adding a LangChain Tool

1. Create a new file in `modules/tools/` (e.g., `modules/tools/my_tool.py`) or add to an existing category file
2. Define tool with `@tool("tool_name")` decorator
3. Import any required clients/modules
4. Import and add to `get_vectorless_tools()` return list in `modules/tools/__init__.py`
5. Update `modules/system_prompts/general_prompt.py` with tool description
6. Restart the `app` service

### 14.3 Adding a Huey Task

1. Define `@huey.task()` function in `tasks/tasks.py`
2. Add to `tasks/__init__.py` exports
3. If schedulable: add to `task_map` in `schedule_task()` function
4. Update `modules/system_prompts/general_prompt.py` Available Tasks section
5. Huey worker auto-reloads on container restart

---

## 15. Environment Quick Reference

| Variable | Required | Used By |
|----------|----------|---------|
| `MODEL_PROVIDER` | Yes | `agent_mod.py`, `agent_utils.py` |
| `EMBEDDING_PROVIDER` | No | `embedder.py` (default: `openai`) |
| `OPENAI_API_KEY` | If provider=openai | `agent_utils.py`, `embedder.py` |
| `GOOGLE_API_KEY` | If provider=google | `agent_utils.py`, `embedder.py` |
| `GROQ_API_KEY` | If provider=groq | `agent_utils.py` |
| `OPEN_ROUTER_API_KEY` | If provider=openrouter | `agent_utils.py`, `embedder.py` |
| `NVIDIA_API_KEY` | If provider=nvidia | `agent_utils.py`, `embedder.py` |
| `OPENAI_EMBEDDINGS_MODEL` | No | `embedder.py` |
| `OPEN_ROUTER_EMBEDDINGS_MODEL` | No | `embedder.py` |
| `REDIS_URL` | Yes | `tasks/tasks.py` (Huey) |
| `PAGE_INDEX_API_KEY` | No | `tasks/tasks.py`, `mcps/__init__.py` |
| `EMAIL_HOST_USER` | No | `tasks/tasks.py` (SMTP) |
| `EMAIL_HOST_PASSWORD` | No | `tasks/tasks.py` (SMTP) |
| `OPENWEATHERMAP_API_KEY` | No | `modules/tools/weather.py` |
| `MY_EMAIL` | No | `modules/system_prompts/general_prompt.py` |
| `DATASTORE_DIR` | Yes | `app.py`, `mcps/mcp_fs.py`, `modules/tools/file_management.py` |
| `INTERNAL_DIR` | Yes | `app.py`, `modules/agent_mod.py` |
| `SQLITE_DB_PATH` | Yes | `mcps/mcp_sql.py` |
| `DOWNLOADS_DIR` | Yes | `mcps/mcp_downloader.py` |
| `CHROMA_DIR` | No | `modules/embedder.py` (default: `./datastore/internal/chroma`) |

---

## 16. Key Code Snippets

### Initialize Agent (from `app.py` lifespan)

```python
agent = MCPAgentModule()
await agent.init()
```

### Invoke Agent (from `app.py` `/api/chat`)

```python
response = await agent.invoke_agent(question=request.message)
answer = response.content if hasattr(response, "content") else str(response)
```

### Create LLM (from `modules/agent_utils.py`)

```python
llm = create_llm(
    model_provider=os.getenv("MODEL_PROVIDER"),
    model_name=os.getenv("MODEL"),
    model_temperature=float(os.getenv("MODEL_TEMPERATURE", "0.5")),
    max_tokens=int(os.getenv("MAX_TOKENS", "1500")),
)
```

### Create Embeddings (from `modules/embedder.py`)

```python
embeddings = create_embeddings(
    provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
    model_name=os.getenv("OPENAI_EMBEDDINGS_MODEL"),
)
```

### Embed a File (from `modules/embedder.py`)

```python
result = embed_and_store(
    source="./datastore/docs/report.pdf",
    collection_name="reports",
)
# Returns: {"ok": True, "chunks": 47, "collection": "reports", "persist_dir": "./datastore/internal/chroma"}
```

### Query Embedded Data (from `modules/embedder.py`)

```python
result = query_documents(
    query="What are the main findings?",
    collection_name="reports",
    k=5,
)
# Returns: {"ok": True, "query": "...", "results": [{"content": "...", "metadata": {...}}]}
```

### Register MCP Tools (from `mcps/__init__.py`)

```python
MCP_TOOLS = {
    "server-name": {
        "url": "http://host:port/mcp/",
        "transport": "streamable-http",
    },
    "another-server": {
        "command": "uv",
        "transport": "stdio",
        "args": ["run", "package-name"],
        "env": {"KEY": "value"},
    },
}
```

---

**End of AGENTS.md**

> Keep this file updated when adding new tools, MCP servers, embedding providers, or changing architecture.
