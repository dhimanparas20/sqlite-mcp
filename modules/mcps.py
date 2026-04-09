from os import getenv

MCP_TOOLS = {
    "sqlite-local": {
        "url": getenv("DEFAULT_MCP_SERVER_URL", "http://127.0.0.1:8000/mcp/"),
        "transport": "streamable-http",
    },
    "ddg-search": {
        "command": "uvx",
        "transport": "stdio",
        "args": ["duckduckgo-mcp-server"],
        "env": {
            "DDG_SAFE_SEARCH": "MODERATE",
            "DDG_REGION": "in-en",
        },
    },
    "fetch": {
        "command": "uvx",
        "transport": "stdio",
        "args": ["mcp-server-fetch"],
    },
    "git": {
        "command": "uvx",
        "transport": "stdio",
        "args": ["mcp-server-git"],
    },
    "time": {
        "command": "uvx",
        "transport": "stdio",
        "args": ["mcp-server-time"],  # Removed the broken flag
    },
}
