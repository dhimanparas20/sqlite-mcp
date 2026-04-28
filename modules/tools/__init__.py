"""LangChain tools package — split by category.

All tools are re-exported here for convenience. The public entry point
for the agent is ``get_vectorless_tools()``.
"""

from typing import List

from modules.tools.background import (
    get_all_tasks_tool,
    get_background_task_status_tool,
    index_files_tool,
    index_urls_tool,
    schedule_task_tool,
    send_email_task_tool,
    sleep_tool,
)
from modules.tools.datetime import get_system_datetime_tool
from modules.tools.embedding import (
    clear_chroma_collection_tool,
    delete_chroma_collection_tool,
    embed_file_tool,
    list_chroma_collections_tool,
    query_embedded_data_tool,
)
from modules.tools.file_management import file_management_tools
from modules.tools.weather import weather_tool

__all__ = [
    # background
    "get_background_task_status_tool",
    "get_all_tasks_tool",
    "index_files_tool",
    "index_urls_tool",
    "schedule_task_tool",
    "send_email_task_tool",
    "sleep_tool",
    # datetime
    "get_system_datetime_tool",
    # embedding
    "embed_file_tool",
    "query_embedded_data_tool",
    "list_chroma_collections_tool",
    "clear_chroma_collection_tool",
    "delete_chroma_collection_tool",
    # weather
    "weather_tool",
    # file management (list of tools, not single symbols)
    # accessed via file_management_tools
    # entry point
    "get_vectorless_tools",
]


def get_vectorless_tools() -> List:
    """Get all vectorless/index tools as a list.

    Returns:
        List of LangChain tool functions for background tasks.
    """
    return [
        index_files_tool,
        index_urls_tool,
        sleep_tool,
        get_background_task_status_tool,
        get_all_tasks_tool,
        send_email_task_tool,
        schedule_task_tool,
        get_system_datetime_tool,
        weather_tool,
        embed_file_tool,
        query_embedded_data_tool,
        list_chroma_collections_tool,
        clear_chroma_collection_tool,
        delete_chroma_collection_tool,
        *file_management_tools,
    ]
