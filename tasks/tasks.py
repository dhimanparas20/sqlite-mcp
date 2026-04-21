from __future__ import annotations

import os
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Union, Dict, Any

import requests
from pageindex import PageIndexClient

from modules import get_logger

logger = get_logger(__name__, show_time=True)
from huey import RedisHuey

huey = RedisHuey("MCP HUB", url=os.getenv("REDIS_URL"), utc=False)
pi = PageIndexClient(api_key=os.getenv("PAGE_INDEX_API_KEY"))
logger.info("Huey initialized with Redis URL from env")


# A function to get the status of a job
def get_job_status(job_id: str) -> dict:
    """
    Get the status and result of a Huey job by ID.
    Returns: dict with status and (if available) result or error.
    """
    logger.info(f"Checking status for job ID: {job_id}")

    # preserve=True keeps the result in Redis for future status checks
    res = huey.result(job_id, preserve=True)
    if res is not None:
        return {"status": "finished", "result": res}
    # Check if job is still in the queue (pending or running)
    task_data = huey.storage.peek_data(job_id)
    if task_data:
        return {"status": "pending", "result": None}
    # If neither, job is not found or expired
    return {"status": "not_found", "result": None}


def get_all_tasks() -> dict:
    """
    Get all tasks across different states in Huey queue.
    Returns: dict with scheduled (eta) and pending keys.
    """
    result = {
        "scheduled": [],
        "pending": [],
    }

    for task in huey.scheduled():
        result["scheduled"].append(
            {
                "id": task.id,
                "name": task.name,
                "eta": task.eta.isoformat() if task.eta else None,
            }
        )

    for task in huey.pending():
        result["pending"].append(
            {
                "id": task.id,
                "name": task.name,
            }
        )

    return result


@huey.task(retries=3, retry_delay=5)
def index_documents_task(
    sources: Union[str, List[str]],
    max_workers: int = 10,
    poll_interval: int = 5,
    timeout: int = 300,
) -> List[Dict[str, Any]]:
    """Index documents using PageIndex service."""
    if not sources:
        raise ValueError("Sources cannot be empty")

    if isinstance(sources, str):
        sources = [sources]

    if PageIndexClient is None:
        raise ImportError(
            "pageindex package is required. Install with: pip install pageindex"
        )

    results: List[Dict[str, Any]] = []
    logger.info(f"[index_documents_task] Starting with {len(sources)} sources")

    def _process_single_source(source: str) -> Dict[str, Any]:
        logger.info(f"[index_documents_task] Processing source: {source}")
        try:
            local_path = source

            if source.startswith(("http://", "https://")):
                logger.info(f"[index_documents_task] Downloading {source}")
                filename = source.split("/")[-1]
                local_path = os.path.join("../data", filename)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                if not os.path.exists(local_path):
                    response = requests.get(source, timeout=60)
                    response.raise_for_status()
                    with open(local_path, "wb") as f:
                        f.write(response.content)

            if not os.path.exists(local_path):
                return {"status": "error", "source": source}

            submit_result = pi.submit_document(local_path)
            doc_id = submit_result.get("doc_id")

            start_time = time.time()
            while time.time() - start_time < timeout:
                status_result = pi.get_document(doc_id)
                status = status_result.get("status")

                if status == "completed":
                    return {"status": "completed", "doc_id": doc_id, "source": source}
                elif status in ("failed", "error"):
                    return {"status": "failed", "source": source}

                time.sleep(poll_interval)

            return {"status": "timeout", "source": source}

        except Exception as e:
            logger.error(f"[index_documents_task] Error indexing {source}: {e}")
            return {"status": "error", "source": source}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_single_source, src): src for src in sources}

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    logger.info(f"[index_documents_task] Completed with {len(results)} results")
    return results


@huey.task(retries=3, retry_delay=5)
def send_email_task(
    to: Union[str, List[str]],
    subject: str,
    body: str,
    is_html: bool = False,
):
    """
    Send an email via SMTP.

    Args:
        to: Recipient email address(es)
        subject: Email subject
        body: Email body content
        is_html: If True, body is sent as HTML; otherwise as plain text
    """
    logger.info(f"[send_email_task] Sending email to {to}")

    email_host = os.getenv("EMAIL_HOST_USER")
    email_password = os.getenv("EMAIL_HOST_PASSWORD")

    if not email_host or not email_password:
        raise ValueError(
            "SMTP credentials not configured. Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD env vars."
        )

    recipients = [to] if isinstance(to, str) else to

    msg = MIMEMultipart("alternative")
    msg["From"] = email_host
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    mime_type = "html" if is_html else "plain"
    msg.attach(MIMEText(body, mime_type))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(email_host, email_password)
        server.sendmail(email_host, recipients, msg.as_string())

    logger.info(f"[send_email_task] Email sent successfully to {recipients}")
    return "sent"


@huey.task(retries=3, retry_delay=5)
def test_sleep_task(sleep_time: int = 5):
    logger.info(f"[test_sleep_task] {sleep_time} seconds")
    time.sleep(sleep_time)
    logger.info("[test_sleep_task] completed")
    return "done"


@huey.task(retries=3, retry_delay=5)
def test_schedule_task(data: str):
    logger.info(f"[test_schedule_task] Task executed with data: {data}")
    return "done"


def schedule_task(
    task_name: str,
    args: tuple = (),
    kwargs: dict = None,
    delay: int = None,
    eta: str = None,
) -> dict:
    """Generic scheduler for any Huey task.

    Args:
        task_name: Name of the Huey task to schedule (e.g., 'test_sleep_task', 'send_email_task', 'index_documents_task')
        args: Positional arguments for the task
        kwargs: Keyword arguments for the task
        delay: Schedule to run after this many seconds (optional)
        eta: Schedule to run at this ISO8601 datetime string (optional)

    Returns:
        dict with job_id and status
    """
    task_map = {
        "test_sleep_task": test_sleep_task,
        "test_schedule_task": test_schedule_task,
        "send_email_task": send_email_task,
        "index_documents_task": index_documents_task,
    }

    if task_name not in task_map:
        raise ValueError(
            f"Unknown task: {task_name}. Available tasks: {list(task_map.keys())}"
        )

    task_func = task_map[task_name]
    kwargs = kwargs or {}

    if eta:
        from datetime import datetime

        eta_dt = datetime.fromisoformat(eta.replace("Z", "+00:00"))
        job = task_func.schedule(args=args, kwargs=kwargs, eta=eta_dt)
    elif delay:
        job = task_func.schedule(args=args, kwargs=kwargs, delay=delay)
    else:
        job = task_func(*args, **kwargs)

    logger.info(f"[schedule_task] Scheduled {task_name} with job_id: {job.id}")
    return {"success": True, "id": job.id, "task": task_name}
