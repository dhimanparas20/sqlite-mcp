from os import getenv

MCP_TOOLS = {
    "sqlite-local": {
        "url": getenv("DEFAULT_MCP_SERVER_URL", "http://127.0.0.1:8000/mcp/"),
        "transport": "streamable-http",
    },
    "custom-fs": {
        "url": "http://127.0.0.1:8005/mcp",
        "transport": "streamable-http",
    },
    "downloader": {
        "url": "http://127.0.0.1:8010/mcp",
        "transport": "streamable-http",
    },
    "ddg-search": {
        "command": "uv",
        "transport": "stdio",
        "args": ["run", "duckduckgo-mcp-server"],
        "env": {
            "DDG_SAFE_SEARCH": "MODERATE",
            "DDG_REGION": "in-en",
        },
    },
    "fetch": {
        "command": "uv",
        "transport": "stdio",
        "args": ["run", "mcp-server-fetch"],
    },
    "git": {
        "command": "uv",
        "transport": "stdio",
        "args": ["run", "mcp-server-git"],
    },
    "time": {
        "command": "uv",
        "transport": "stdio",
        "args": ["run", "mcp-server-time"],
    },
    "url-downloader": {
        "command": "uv",
        "transport": "stdio",
        "args": ["run", "mcp-url-downloader", "--path", "/home/paras/Downloads/mcp_downloads"],
        "env": {"DEFAULT_OUTPUT_DIR": "/home/paras/Downloads/mcp_downloads"},
    },
}
