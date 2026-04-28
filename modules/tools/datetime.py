"""System datetime tool."""

from datetime import datetime
from typing import Any, Dict

from langchain.tools import tool

from modules.logger import get_logger

logger = get_logger(__name__)


@tool("get_system_datetime")
def get_system_datetime_tool() -> Dict[str, Any]:
    """Get the current system date and time in a readable format.

    This tool returns the system's local time. ALWAYS use this tool for any
    time-based activities that require knowing the current time or calculating
    durations, delays, or future scheduling times. Do NOT rely on external
    time APIs or assume the time - always fetch it from this tool first.

    Returns:
        Dict containing:
            - datetime: Readable datetime string (e.g., "2026-04-10 23:00:00")
            - iso: ISO8601 formatted datetime
            - timestamp: Unix timestamp
            - timezone: System timezone (e.g., "Asia/Kolkata")
    """
    now = datetime.now()
    logger.info(f"[get_system_datetime_tool] now: {now}")
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "iso": now.isoformat(),
        "timestamp": int(now.timestamp()),
        "timezone": str(now.astimezone().tzinfo) if now.astimezone().tzinfo else "Unknown",
    }
