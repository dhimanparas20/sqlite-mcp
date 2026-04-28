"""Background task and scheduling tools."""

from typing import Any, Dict, List, Optional, Union

from langchain.tools import tool

from modules.logger import get_logger
from tasks import (
    get_all_tasks,
    get_job_status,
    index_documents_task,
    schedule_task,
    send_email_task,
    test_sleep_task,
)

logger = get_logger(__name__)


@tool("get_background_task_status")
def get_background_task_status_tool(job_id: str) -> Dict[str, Any]:
    """Get the status of a background task by its job ID.

    Use this to check if a previously submitted background task has completed.
    Returns the task status (pending, finished, not_found) and any result if completed.

    Args:
        job_id: The unique identifier of the background task.

    Returns:
        Dict containing:
            - status: 'pending', 'finished', or 'not_found'
            - result: The task result if finished, otherwise None
    """
    logger.info(f"[get_background_task_status_tool] : {job_id}")
    status = get_job_status(job_id)
    logger.info(f"[get_background_task_status_tool] || {status}")
    return status


@tool("get_all_tasks")
def get_all_tasks_tool() -> Dict[str, Any]:
    """Get all tasks in the Huey queue.

    Returns all tasks across different states: scheduled (eta tasks),
    pending (waiting in queue), and completed results.

    Returns:
        Dict containing:
            - scheduled: List of tasks scheduled to run at specific time
            - pending: List of tasks waiting in queue
            - results: List of completed tasks with their results
    """
    logger.info("[get_all_tasks_tool] Fetching all tasks")
    return get_all_tasks()


@tool("index_files")
def index_files_tool(file_paths: Union[str, List[str]]) -> Dict[str, Any]:
    """Index local files (pdf, md, txt, csv, etc.) to PageIndex for searching.

    This is an asynchronous background task - returns immediately with a job ID.
    Use get_background_task_status with the job ID to check completion.

    Args:
        file_paths: Single file path string or list of file paths to index.

    Returns:
        Dict containing:
            - success: True if queued successfully
            - id: Job ID to track progress
    """
    logger.info(f"[index_files_tool] : {file_paths}")
    job = index_documents_task(sources=file_paths)
    logger.info(f"[index_files_tool] {job.id}")
    return {"success": True, "id": job.id}


@tool("index_urls")
def index_urls_tool(urls: Union[str, List[str]]) -> Dict[str, Any]:
    """Index remote file URLs (pdf, md, txt, csv, etc.) to PageIndex for searching.

    Downloads the file, indexes it asynchronously, and returns a job ID.
    Use get_background_task_status with the job ID to check completion.

    Args:
        urls: Single URL string or list of URLs to index.

    Returns:
        Dict containing:
            - success: True if queued successfully
            - id: Job ID to track progress
    """
    logger.info(f"[index_urls_tool] : {urls}")
    job = index_documents_task(sources=urls)
    logger.info(f"[index_urls_tool] || {job.id}")
    return {"success": True, "id": job.id}


@tool("sleep")
def sleep_tool(sleep_time: int = 5) -> Dict[str, Any]:
    """Queue a background sleep task for a specified duration.

    Useful for testing or delaying other operations.

    Args:
        sleep_time: Time to sleep in seconds (default: 5).

    Returns:
        Dict containing:
            - success: True if queued successfully
            - id: Job ID to track progress
    """
    job = test_sleep_task(sleep_time=sleep_time)
    logger.info(f"[sleep_tool] added to queue: {job.id}")
    return {"success": True, "id": job.id}


@tool("send_email_task")
def send_email_task_tool(
    to: Union[str, List[str]],
    subject: str,
    body: str,
    is_html: bool = False,
) -> Dict[str, Any]:
    """Send an email via SMTP.

    Queues an email to be sent asynchronously. Requires EMAIL_HOST_USER and
    EMAIL_HOST_PASSWORD environment variables to be configured.

    Args:
        to: Recipient email address(es) - single string or list of addresses.
        subject: Email subject line.
        body: Email body content.
        is_html: If True, body is sent as HTML; otherwise as plain text (default: False).

    Returns:
        Dict containing:
            - success: True if queued successfully
            - id: Job ID to track progress
    """
    job = send_email_task(to=to, subject=subject, body=body, is_html=is_html)
    logger.info(f"[send_email_task_tool] added to queue: {job.id}")
    return {"success": True, "id": job.id}


@tool("schedule_task")
def schedule_task_tool(
    task_name: str,
    task_args: Optional[List[Any]] = None,
    task_kwargs: Optional[Dict[str, Any]] = None,
    delay: Optional[int] = None,
    eta: Optional[str] = None,
) -> Dict[str, Any]:
    """Schedule any Huey task to run in the future.

    A generic scheduler that can queue any registered Huey task with optional
    delay or specific execution time.

    Available tasks:
    - test_sleep_task: Sleep for specified seconds (kwargs: sleep_time)
    - test_schedule_task: Generic test task (args: [data])
    - send_email_task: Send email (kwargs: to, subject, body, is_html)
    - index_documents_task: Index files/URLs (kwargs: sources, max_workers, poll_interval, timeout)

    Args:
        task_name: Name of the task to schedule (e.g., 'send_email_task').
        task_args: List of positional arguments for the task.
        task_kwargs: Dict of keyword arguments for the task.
        delay: Schedule to run after this many seconds (e.g., 180 for 3 minutes).
        eta: Schedule to run at specific ISO8601 datetime (e.g., '2026-04-10T18:00:00').

    Returns:
        Dict containing:
            - success: True if scheduled successfully
            - id: Job ID to track progress
            - task: Name of the scheduled task
    """
    logger.info(
        f"[schedule_task_tool] task: {task_name}, task_args: {task_args}, "
        f"task_kwargs: {task_kwargs}, delay: {delay}, eta: {eta}"
    )
    result = schedule_task(
        task_name=task_name,
        args=task_args or (),
        kwargs=task_kwargs,
        delay=delay,
        eta=eta,
    )
    logger.info(f"[schedule_task_tool] result: {result}")
    return result
