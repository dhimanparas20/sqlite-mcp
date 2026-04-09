MCP_TOOLS = {
    "sqlite-mcp": {"url": "http://127.0.0.1:8000/mcp/", "transport": "streamable-http"},
    "ddg-search": {
        "command": "uvx",
        "transport": "stdio",
        "args": ["duckduckgo-mcp-server"],
        "env": {
            "DDG_SAFE_SEARCH": "MODERATE",  # Options: "STRICT", "MODERATE", "OFF"
            "DDG_REGION": "in-en",  # India (English)
        },
    },
}
