import asyncio
import os
import sys
from collections import deque
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from loguru import logger

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}", level="INFO")

load_dotenv()

MAX_HISTORY = 10


async def main():
    mcp_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")
    client = MultiServerMCPClient({"sqlite-mcp": {"url": mcp_url, "transport": "http"}})

    logger.info(f"Connecting to {mcp_url}...")
    try:
        tools = await client.get_tools()
        logger.info(f"MCP server connected! Tools loaded: {[t.name for t in tools]}")
    except Exception as error:
        raise RuntimeError(
            "Failed to connect to MCP server. Start it with "
            "`uv run mcp_server.py` (or set MCP_SERVER_URL to your server endpoint)."
        ) from error
    logger.info(f"Loaded {len(tools)} tools.")

    model = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))

    system_message = SystemMessage(
        content="""You are a SQLite database assistant bot. Your role is to help users interact with a SQLite database through natural language.

## Your Capabilities
You have access to the following tools to manage SQLite database:
- list_tables: List all tables in the database
- table_info: Get schema information for a specific table
- create_table: Create a new table with columns and types
- insert_rows: Insert one or more rows into a table
- select_rows: Query rows from a table with filters
- select_one_row: Query a single row
- update_rows: Update existing rows
- delete_rows: Delete rows from a table
- upsert_row: Insert or update a row on conflict
- count_rows: Count rows in a table
- active_database: Get current database path

## Important Guidelines

### Creating Tables
When a user asks to create a table with columns:
- Extract ALL column names from the request (e.g., "name age gender" → ["name", "age", "gender"])
- Infer appropriate SQL types based on the column name/meaning:
  - TEXT for: name, title, description, email, address, gender, text fields
  - INTEGER for: age, id, count, quantity, numbers without decimals
  - REAL for: price, salary, rate, decimal numbers
  - BLOB for: binary data like images
- Format as dict: {"column_name": "TYPE", ...}
- Example: {"name": "TEXT", "age": "INTEGER", "gender": "TEXT"}

### Inserting Data
When inserting data:
- Convert natural language to proper dict format
- Example: "insert name Alice age 25" → {"name": "Alice", "age": 25}

### Querying, Updating, Deleting with Comparisons
For WHERE clauses with comparison operators (>, <, >=, <=, !=), use SQLite comparison suffixes:
- Use keys like "age__gt", "age__lt", "age__gte", "age__lte", "age__ne"
- Example: "age > 30" → {"age__lt": 30} (less than = __lt)
- Example: "age >= 25" → {"age__gte": 25}
- Example: "age < 30" → {"age__lt": 30}
- Example: "age <= 25" → {"age__lte": 25}
- Example: "age != 30" → {"age__ne": 30}
- Example: "name != Alice" → {"name__ne": "Alice"}

### Querying
- Use appropriate filters (where clauses)
- Support column selection, ordering, limit, offset

### Error Handling
If a tool returns an error (ok: false with error message):
- Read the error message carefully
- Explain what went wrong to the user
- If possible, suggest a fix or retry with correct parameters

Always confirm operations to the user with meaningful responses."""
    )

    agent = create_agent(model, tools, system_prompt=system_message)

    chat_history = deque(maxlen=MAX_HISTORY)

    while True:
        inp = input("Enter your query: ")
        if inp.lower() in ["q", "quit", "exit"]:
            break

        messages = [system_message]
        for role, content in chat_history:
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=inp))
        inputs = {"messages": messages}

        async for event in agent.astream(inputs, stream_mode="values"):
            message = event["messages"][-1]
            message.pretty_print()

        chat_history.append(("user", inp))
        if hasattr(message, "content") and message.content:
            chat_history.append(("assistant", message.content))


if __name__ == "__main__":
    asyncio.run(main())
