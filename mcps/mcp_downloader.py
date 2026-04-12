from __future__ import annotations

import aiohttp
import asyncio
import os
from datetime import datetime
from fastmcp import FastMCP
from pathlib import Path
from starlette.requests import Request
from starlette.responses import JSONResponse
from typing import Any

from modules.logger import get_logger

logger = get_logger("DOWNLOADER")

DOWNLOADS_SUBDIR = "downloads"

DEFAULT_DOWNLOAD_DIR = os.getenv(
    "DOWNLOADS_DIR",
    str(Path(__file__).resolve().parent.parent / "datastore" / DOWNLOADS_SUBDIR),
)

DOWNLOAD_DIR = Path(DEFAULT_DOWNLOAD_DIR)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 1024 * 1024
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=300, connect=30)

mcp = FastMCP("Downloader", tasks=False)


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def _safe_filename(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path
    if not path or path == "/":
        filename = f"download_{int(datetime.now().timestamp())}"
    else:
        filename = os.path.basename(path)
        if not filename:
            filename = f"download_{int(datetime.now().timestamp())}"

    valid_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._"
    return "".join(c if c in valid_chars else "_" for c in filename)


async def _download_with_progress(
    url: str,
    destination: Path,
    timeout: aiohttp.ClientTimeout = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.head(url) as head_resp:
                if head_resp.status != 200:
                    return {
                        "ok": False,
                        "error": f"URL not accessible: HTTP {head_resp.status}",
                    }

                content_length = int(head_resp.headers.get("content-length", 0))
                content_type = head_resp.headers.get("content-type", "unknown")
                filename = head_resp.headers.get("content-disposition", "")
                if "filename=" in filename:
                    filename = filename.split("filename=")[1].strip('"')
                else:
                    filename = _safe_filename(url)

                final_path = destination / filename
                if final_path.exists():
                    base_name = final_path.stem
                    ext = final_path.suffix
                    counter = 1
                    while final_path.exists():
                        final_path = destination / f"{base_name}_{counter}{ext}"
                        counter += 1

            downloaded = 0
            start_time = datetime.now()

            async with session.get(url) as response:
                if response.status != 200:
                    return {
                        "ok": False,
                        "error": f"Download failed: HTTP {response.status}",
                    }

                with open(final_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if content_length:
                            progress = (downloaded / content_length) * 100
                            logger.info(
                                f"[download] {filename}: {progress:.1f}% ({_format_size(downloaded)}/{_format_size(content_length)})"
                            )

            elapsed = (datetime.now() - start_time).total_seconds()
            speed = downloaded / elapsed if elapsed > 0 else 0

            logger.info(
                f"[download] Completed: {final_path.name} ({_format_size(downloaded)}) in {elapsed:.1f}s"
            )

            return {
                "ok": True,
                "filename": final_path.name,
                "path": str(final_path.relative_to(Path(__file__).parent.parent)),
                "size_bytes": downloaded,
                "size_readable": _format_size(downloaded),
                "content_type": content_type,
                "download_time_seconds": round(elapsed, 2),
                "speed_bps": int(speed),
                "speed_readable": _format_size(int(speed)) + "/s",
            }
    except asyncio.TimeoutError:
        logger.error(f"[download] Timeout: {url}")
        return {"ok": False, "error": "Download timeout"}
    except aiohttp.ClientError as e:
        logger.error(f"[download] Client error: {e}")
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.error(f"[download] Error: {e}")
        return {"ok": False, "error": str(e)}


@mcp.tool(
    name="download_file",
    description="Download a file from a URL to the downloads directory.",
    tags={"enabled"},
)
async def download_file(
    url: str,
    custom_filename: str | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Download a file from a URL.

    Args:
        url: The URL to download from.
        custom_filename: Optional custom filename for the downloaded file.
        timeout: Download timeout in seconds (default 300).

    Returns:
        dict: Download result with file path and size.
    """
    if not url or not url.strip():
        logger.error("[download_file] URL is required")
        return {"ok": False, "error": "URL is required"}

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        logger.error("[download_file] Invalid URL: must start with http:// or https://")
        return {
            "ok": False,
            "error": "Invalid URL: must start with http:// or https://",
        }

    logger.info(f"[download_file] Starting download: {url}")

    timeout_obj = aiohttp.ClientTimeout(total=timeout, connect=30)

    if custom_filename:
        final_path = DOWNLOAD_DIR / custom_filename
        if final_path.exists():
            base_name = final_path.stem
            ext = final_path.suffix
            counter = 1
            while final_path.exists():
                final_path = DOWNLOAD_DIR / f"{base_name}_{counter}{ext}"
                counter += 1

        try:
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return {
                            "ok": False,
                            "error": f"Download failed: HTTP {response.status}",
                        }

                    downloaded = 0
                    content_length = int(response.headers.get("content-length", 0))

                    with open(final_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if content_length:
                                progress = (downloaded / content_length) * 100
                                logger.info(
                                    f"[download] {custom_filename}: {progress:.1f}%"
                                )

                    return {
                        "ok": True,
                        "filename": final_path.name,
                        "path": str(
                            final_path.relative_to(Path(__file__).parent.parent)
                        ),
                        "size_bytes": downloaded,
                        "size_readable": _format_size(downloaded),
                    }
        except Exception as e:
            logger.error(f"[download_file] Error: {e}")
            if final_path.exists():
                os.remove(final_path)
            return {"ok": False, "error": str(e)}
    else:
        return await _download_with_progress(url, DOWNLOAD_DIR, timeout_obj)


@mcp.tool(
    name="download_batch",
    description="Download multiple files from a list of URLs.",
    tags={"enabled"},
)
async def download_batch(
    urls: list[str],
    timeout: int = 300,
    stop_on_error: bool = False,
) -> dict[str, Any]:
    """Download multiple files concurrently.

    Args:
        urls: List of URLs to download.
        timeout: Download timeout in seconds for each file.
        stop_on_error: Stop if any download fails.

    Returns:
        dict: Batch download results.
    """
    if not urls:
        return {"ok": False, "error": "No URLs provided"}

    logger.info(f"[download_batch] Starting batch download of {len(urls)} files")

    timeout_obj = aiohttp.ClientTimeout(total=timeout, connect=30)
    results = []

    for url in urls:
        result = await _download_with_progress(url.strip(), DOWNLOAD_DIR, timeout_obj)
        results.append({"url": url, **result})

        if not result.get("ok") and stop_on_error:
            logger.warning(
                f"[download_batch] Stopping due to error: {result.get('error')}"
            )
            break

    successful = sum(1 for r in results if r.get("ok"))
    failed = len(results) - successful

    logger.info(f"[download_batch] Completed: {successful} successful, {failed} failed")

    return {
        "ok": True,
        "total": len(urls),
        "successful": successful,
        "failed": failed,
        "results": results,
    }


@mcp.tool(
    name="list_downloads",
    description="List all downloaded files in the downloads directory.",
    tags={"enabled"},
)
def list_downloads() -> dict[str, Any]:
    """List all downloaded files.

    Returns:
        dict: List of downloaded files with details.
    """
    if not DOWNLOAD_DIR.exists():
        logger.info("[list_downloads] Downloads directory does not exist")
        return {"ok": True, "files": [], "count": 0}

    files = []
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file():
            stat = f.stat()
            files.append(
                {
                    "name": f.name,
                    "path": str(f.relative_to(Path(__file__).parent.parent)),
                    "size_bytes": stat.st_size,
                    "size_readable": _format_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    files.sort(key=lambda x: x["modified"], reverse=True)
    logger.info(f"[list_downloads] Listed {len(files)} files")
    return {"ok": True, "files": files, "count": len(files)}


@mcp.tool(
    name="get_download_info",
    description="Get information about a specific downloaded file.",
    tags={"enabled"},
)
def get_download_info(filename: str) -> dict[str, Any]:
    """Get details of a downloaded file.

    Args:
        filename: Name of the file.

    Returns:
        dict: File information.
    """
    file_path = DOWNLOAD_DIR / filename

    if not file_path.exists():
        logger.error(f"[get_download_info] File not found: {filename}")
        return {"ok": False, "error": f"File not found: {filename}"}

    stat = file_path.stat()
    logger.info(f"[get_download_info] Retrieved info for: {filename}")

    return {
        "ok": True,
        "name": file_path.name,
        "path": str(file_path.relative_to(Path(__file__).parent.parent)),
        "absolute_path": str(file_path),
        "size_bytes": stat.st_size,
        "size_readable": _format_size(stat.st_size),
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


@mcp.tool(
    name="delete_download",
    description="Delete a downloaded file from the downloads directory.",
    tags={"enabled"},
)
def delete_download(filename: str) -> dict[str, Any]:
    """Delete a downloaded file.

    Args:
        filename: Name of the file to delete.

    Returns:
        dict: Operation status.
    """
    file_path = DOWNLOAD_DIR / filename

    if not file_path.exists():
        logger.error(f"[delete_download] File not found: {filename}")
        return {"ok": False, "error": f"File not found: {filename}"}

    try:
        os.remove(file_path)
        logger.info(f"[delete_download] Deleted: {filename}")
        return {"ok": True, "filename": filename}
    except Exception as e:
        logger.error(f"[delete_download] Error: {e}")
        return {"ok": False, "error": str(e)}


@mcp.tool(
    name="delete_all_downloads",
    description="Delete all downloaded files from the downloads directory.",
    tags={"enabled"},
)
def delete_all_downloads() -> dict[str, Any]:
    """Delete all downloaded files.

    Returns:
        dict: Operation status with list of deleted files.
    """
    if not DOWNLOAD_DIR.exists():
        return {"ok": True, "deleted": [], "count": 0}

    deleted = []
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file():
            try:
                os.remove(f)
                deleted.append(f.name)
            except Exception as e:
                logger.error(f"[delete_all_downloads] Error deleting {f.name}: {e}")

    logger.info(f"[delete_all_downloads] Deleted {len(deleted)} files")
    return {"ok": True, "deleted": deleted, "count": len(deleted)}


@mcp.tool(
    name="get_download_dir",
    description="Get the current downloads directory path.",
    tags={"enabled"},
)
def get_download_dir() -> dict[str, Any]:
    """Get downloads directory info.

    Returns:
        dict: Directory path and stats.
    """
    if not DOWNLOAD_DIR.exists():
        return {"ok": True, "path": str(DOWNLOAD_DIR), "exists": False}

    total_size = sum(f.stat().st_size for f in DOWNLOAD_DIR.iterdir() if f.is_file())
    file_count = sum(1 for f in DOWNLOAD_DIR.iterdir() if f.is_file())

    logger.info(f"[get_download_dir] Download dir: {DOWNLOAD_DIR}")
    return {
        "ok": True,
        "path": str(DOWNLOAD_DIR),
        "relative_path": str(DOWNLOAD_DIR.relative_to(Path(__file__).parent.parent)),
        "exists": True,
        "total_size_bytes": total_size,
        "total_size_readable": _format_size(total_size),
        "file_count": file_count,
    }


@mcp.tool(
    name="check_url",
    description="Check if a URL is accessible and get metadata.",
    tags={"enabled"},
)
async def check_url(url: str, timeout: int = 10) -> dict[str, Any]:
    """Check URL accessibility and get metadata.

    Args:
        url: The URL to check.
        timeout: Request timeout in seconds.

    Returns:
        dict: URL metadata including size, content-type, etc.
    """
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "Invalid URL"}

    timeout_obj = aiohttp.ClientTimeout(total=timeout, connect=5)

    try:
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            async with session.head(url) as response:
                if response.status != 200:
                    return {
                        "ok": False,
                        "error": f"URL not accessible: HTTP {response.status}",
                    }

                content_length = response.headers.get("content-length", "unknown")
                content_type = response.headers.get("content-type", "unknown")
                last_modified = response.headers.get("last-modified", "unknown")

                logger.info(f"[check_url] URL accessible: {url}")
                return {
                    "ok": True,
                    "url": url,
                    "status_code": response.status,
                    "content_length": content_length,
                    "content_type": content_type,
                    "last_modified": last_modified,
                    "accessible": True,
                }
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Connection timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"}, 200)


if __name__ == "__main__":
    logger.info(f"[init] Download directory: {DOWNLOAD_DIR}")
    try:
        mcp.run(
            transport="streamable-http",
            host=os.getenv("FASTMCP_HOST", "0.0.0.0"),
            port=int(os.getenv("FASTMCP3_PORT", "8010")),
            log_level=os.getenv("FASTMCP_LOG_LEVEL", "INFO"),
            stateless_http=False,
            show_banner=True,
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        mcp.close()
    except Exception as e:
        import traceback
        import sys

        traceback.print_exc()
        logger.error(f"Error starting server: {e}")
        sys.exit(1)
