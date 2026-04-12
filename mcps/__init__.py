import os
from dotenv import load_dotenv

load_dotenv()

MCP_TOOLS = {
    "sqlite-local": {
        "url": "http://mcp_sql:8000/mcp/",
        "transport": "streamable-http",
    },
    # Not using this one because we already have a tool for it
    # "custom-fs": {
    #     "url": "http://mcp_fs:8005/mcp",
    #     "transport": "streamable-http",
    # },
    "downloader": {
        "url": "http://mcp_downloader:8010/mcp",
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
    "pageindex": {
        "transport": "http",
        "url": "https://api.pageindex.ai/mcp",
        "headers": {"Authorization": f"Bearer {os.getenv('PAGE_INDEX_API_KEY')}"},
    },
    # "openweather-mcp": {
    #     "command": "uvx",
    #     "transport": "stdio",
    #     "args": ["openweather-mcp"],
    #     "env": {"OPENWEATHER_API_KEY": "<open_weather_key>"},
    # },
    # "mongo-mcp": {
    #     "command": "uvx",
    #     "transport": "stdio",
    #     "args": ["mongo-mcp"],
    #     "env": {
    #         "MONGODB_URI": "<mongo_db_uri>=",
    #         # "MONGODB_DEFAULT_DB": "MONGODB_DEFAULT_DB",
    #         # "LOG_LEVEL": "INFO"
    #     },
    # },
}
