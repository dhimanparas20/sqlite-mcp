"""LangChain tools for document indexing and querying using PageIndex."""

import os
from typing import List, Union

from dotenv import load_dotenv
from langchain.tools import tool
from pageindex import PageIndexClient

from modules import get_logger
from tasks import index_documents_task, test_sleep_task, get_job_status

logger = get_logger(__name__)

load_dotenv()


@tool("get_background_task_status")
def get_background_task_status_tool(
    job_id: str,
) -> dict:
    """Get the status of a background task by ID.

    Args:
        job_id: The ID of the background task.

    Returns:
        JSON string with the status of the background task.
    """
    logger.info(f"[get_background_task_status_tool] : {job_id}")
    status = get_job_status(job_id)
    logger.info(f"[get_background_task_status_tool] || {status}")
    return status


@tool("index_files")
def index_files_tool(
    file_paths: Union[str, List[str]],
) -> dict:
    """Index local files (pdf, md, txt, csv, etc.) to PageIndex for searching.

    Args:
        file_paths: Single file path or list of file paths to index.
    Returns:
        JSON string with indexed document info (doc_id, name, status, source).
    """
    logger.info(f"[index_files_tool] : {file_paths}")
    job = index_documents_task(sources=file_paths)
    logger.info(f"[index_files_tool] {job.id}")
    return {"success": True, "id": job.id}


@tool("index_urls")
def index_urls_tool(
    urls: Union[str, List[str]],
) -> dict:
    """Index remote file URLs (pdf, md, txt, csv, etc.) to PageIndex for searching.

    Downloads the file, indexes it, and returns the document info.

    Args:
        urls: Single URL or list of URLs to index.

    Returns:
        JSON string with indexed document info (doc_id, name, status, source).
    """
    logger.info(f"[index_urls_tool] : {urls}")
    job = index_documents_task(sources=urls)
    logger.info(f"[index_urls_tool] || {job.id}")
    return {"success": True, "id": job.id}


@tool("sleep")
def sleep_tool(sleep_time: int = 5) -> dict:
    """Sleep for a specified time.

    Args:
        sleep_time: Time to sleep in seconds.

    Returns:
        String indicating the sleep is done.
    """
    job = test_sleep_task(sleep_time=sleep_time)
    logger.info(f"[sleep_tool] added to queue: {job.id}")
    return {"success": True, "id": job.id}


def get_vectorless_tools():
    """Get all vectorless/index tools as a list."""
    logger.debug("get_vectorless_tools called")
    return [
        index_files_tool,
        index_urls_tool,
        sleep_tool,
        get_background_task_status_tool,
    ]
