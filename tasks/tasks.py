from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Union, Dict, Any

import requests
from pageindex import PageIndexClient

from modules import get_logger

logger = get_logger(__name__)
from huey import FileHuey

huey = FileHuey("MCP HUB", path="/app/datastore/internal/huey")
pi = PageIndexClient(api_key=os.getenv("PAGE_INDEX_API_KEY"))
logger.info("Huey initialized with path: /app/datastore/internal/huey")


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
        raise ImportError("pageindex package is required. Install with: pip install pageindex")

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
def test_sleep_task(sleep_time: int = 5):
    logger.info(f"[test_sleep_task] {sleep_time} seconds")
    time.sleep(sleep_time)
    logger.info("[test_sleep_task] completed")
    return "done"
