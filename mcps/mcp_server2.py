from fastmcp import FastMCP
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any
from modules.logger import get_logger

logger = get_logger("FILESYSTEM")

mcp = FastMCP("filesystem")
ROOT = os.getcwd()
if ROOT.endswith("\\"):
    ROOT = ROOT[:-1]


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def safe(path: str) -> str:
    full = os.path.normpath(os.path.join(ROOT, path))
    if not full.startswith(ROOT):
        logger.warning(f"[safe] Access denied: {path} outside allowed directory")
        raise ValueError("Access denied: outside allowed directory")
    return full


@mcp.tool(
    name="list_directory",
    description="List contents of a directory with optional filtering.",
    tags={"enabled"},
)
def list_directory(path: str = ".", pattern: str | None = None, include_hidden: bool = False) -> dict[str, Any]:
    """List contents of a directory.

    Args:
        path: Path to the directory.
        pattern: Optional glob pattern to filter files.
        include_hidden: Whether to include hidden files (starting with .).

    Returns:
        dict: Directory listing with files and subdirectories.
    """
    full = safe(path)
    if not os.path.exists(full):
        logger.error(f"[list_directory] Directory not found: {path}")
        return {"ok": False, "error": f"Directory not found: {path}"}
    if not os.path.isdir(full):
        logger.error(f"[list_directory] Not a directory: {path}")
        return {"ok": False, "error": f"Not a directory: {path}"}

    items = []
    for item in os.listdir(full):
        if not include_hidden and item.startswith("."):
            continue
        full_path = os.path.join(full, item)
        stat = os.stat(full_path)
        if pattern and not Path(item).match(pattern):
            continue
        items.append(
            {
                "name": item,
                "path": os.path.join(path, item),
                "is_file": os.path.isfile(full_path),
                "is_dir": os.path.isdir(full_path),
                "size_bytes": stat.st_size if os.path.isfile(full_path) else None,
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )

    items.sort(key=lambda x: (not x["is_dir"], x["name"]))
    logger.info(f"[list_directory] Listed {len(items)} items in {path}")
    return {"ok": True, "path": path, "items": items, "count": len(items)}


@mcp.tool(
    name="get_file_info",
    description="Get detailed information about a file.",
    tags={"enabled"},
)
def get_file_info(path: str) -> dict[str, Any]:
    """Get detailed information about a file.

    Args:
        path: Path to the file.

    Returns:
        dict: File details including size, modified time, etc.
    """
    full = safe(path)
    if not os.path.exists(full):
        logger.error(f"[get_file_info] File not found: {path}")
        return {"ok": False, "error": f"File not found: {path}"}

    stat = os.stat(full)
    p = Path(full)
    logger.info(f"[get_file_info] Retrieved info for: {path}")
    return {
        "ok": True,
        "name": p.name,
        "path": path,
        "size_bytes": stat.st_size,
        "size_readable": _format_size(stat.st_size),
        "is_file": p.is_file(),
        "is_dir": p.is_dir(),
        "is_symlink": p.is_symlink(),
        "exists": p.exists(),
        "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "extension": p.suffix,
        "parent": str(p.parent),
    }


@mcp.tool(
    name="read_file",
    description="Read content from a file.",
    tags={"enabled"},
)
def read_file(path: str, max_size: int = 1024 * 1024) -> dict[str, Any]:
    """Read content from a file.

    Args:
        path: Path to the file.
        max_size: Maximum file size to read in bytes (default 1MB).

    Returns:
        dict: File content and metadata.
    """
    full = safe(path)
    if not os.path.exists(full):
        logger.error(f"[read_file] File not found: {path}")
        return {"ok": False, "error": f"File not found: {path}"}
    if not os.path.isfile(full):
        logger.error(f"[read_file] Not a file: {path}")
        return {"ok": False, "error": f"Not a file: {path}"}

    size = os.path.getsize(full)
    if size > max_size:
        logger.error(f"[read_file] File too large: {size} bytes (max {max_size})")
        return {"ok": False, "error": f"File too large: {size} bytes (max {max_size})"}

    with open(full, "r", encoding="utf-8") as f:
        content = f.read()

    logger.info(f"[read_file] Read {len(content)} chars from {path}")
    return {
        "ok": True,
        "path": path,
        "content": content,
        "size_bytes": size,
        "lines": len(content.splitlines()),
    }


@mcp.tool(
    name="write_file",
    description="Write content to a file, creating or overwriting.",
    tags={"enabled"},
)
def write_file(path: str, content: str, create_dirs: bool = True) -> dict[str, Any]:
    """Write content to a file.

    Args:
        path: Path to the file.
        content: Content to write.
        create_dirs: Whether to create parent directories.

    Returns:
        dict: Operation status.
    """
    full = safe(path)

    if create_dirs:
        os.makedirs(os.path.dirname(full), exist_ok=True)

    with open(full, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"[write_file] Wrote {len(content)} chars to {path}")
    return {
        "ok": True,
        "path": path,
        "size_bytes": len(content.encode("utf-8")),
    }


@mcp.tool(
    name="create_file",
    description="Create a new file with optional content.",
    tags={"enabled"},
)
def create_file(path: str, content: str = "", create_dirs: bool = True) -> dict[str, Any]:
    """Create a new file with optional content.

    Args:
        path: Path for the new file.
        content: Content to write to the file.
        create_dirs: Whether to create parent directories if they don't exist.

    Returns:
        dict: Operation status with created file path.
    """
    full = safe(path)

    if create_dirs:
        os.makedirs(os.path.dirname(full), exist_ok=True)
    else:
        if not os.path.exists(os.path.dirname(full)):
            logger.error(f"[create_file] Parent directory does not exist: {os.path.dirname(path)}")
            return {
                "ok": False,
                "error": f"Parent directory does not exist: {os.path.dirname(path)}",
            }

    with open(full, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"[create_file] Created file: {path}")
    return {"ok": True, "path": path, "size_bytes": len(content.encode("utf-8"))}


@mcp.tool(
    name="copy_file",
    description="Copy a file or directory to a new location.",
    tags={"enabled"},
)
def copy_file(source: str, destination: str, overwrite: bool = False) -> dict[str, Any]:
    """Copy a file or directory.

    Args:
        source: Source file or directory path.
        destination: Destination path.
        overwrite: Whether to overwrite if destination exists.

    Returns:
        dict: Operation status.
    """
    src = safe(source)
    dst = safe(destination)

    if not os.path.exists(src):
        logger.error(f"[copy_file] Source not found: {source}")
        return {"ok": False, "error": f"Source not found: {source}"}

    if os.path.exists(dst) and not overwrite:
        logger.error(f"[copy_file] Destination exists: {destination}")
        return {"ok": False, "error": f"Destination exists: {destination}"}

    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        logger.info(f"[copy_file] Copied directory: {source} -> {destination}")
    else:
        shutil.copy2(src, dst)
        logger.info(f"[copy_file] Copied file: {source} -> {destination}")

    return {"ok": True, "source": source, "destination": destination}


@mcp.tool(
    name="move_file",
    description="Move a file or directory to a new location.",
    tags={"enabled"},
)
def move_file(source: str, destination: str, overwrite: bool = False) -> dict[str, Any]:
    """Move a file or directory.

    Args:
        source: Source file or directory path.
        destination: Destination path.
        overwrite: Whether to overwrite if destination exists.

    Returns:
        dict: Operation status.
    """
    src = safe(source)
    dst = safe(destination)

    if not os.path.exists(src):
        logger.error(f"[move_file] Source not found: {source}")
        return {"ok": False, "error": f"Source not found: {source}"}

    if os.path.exists(dst) and not overwrite:
        logger.error(f"[move_file] Destination exists: {destination}")
        return {"ok": False, "error": f"Destination exists: {destination}"}

    if os.path.exists(dst):
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        else:
            os.remove(dst)

    shutil.move(src, dst)
    logger.info(f"[move_file] Moved: {source} -> {destination}")
    return {"ok": True, "source": source, "destination": destination}


@mcp.tool(
    name="delete_file",
    description="Delete a file or directory.",
    tags={"enabled"},
)
def delete_file(path: str) -> dict[str, Any]:
    """Delete a file or directory.

    Args:
        path: Path to delete.

    Returns:
        dict: Operation status.
    """
    full = safe(path)

    if not os.path.exists(full):
        logger.error(f"[delete_file] Path not found: {path}")
        return {"ok": False, "error": f"Path not found: {path}"}

    if os.path.isdir(full):
        shutil.rmtree(full)
        logger.info(f"[delete_file] Deleted directory: {path}")
    else:
        os.remove(full)
        logger.info(f"[delete_file] Deleted file: {path}")

    return {"ok": True, "path": path}


@mcp.tool(
    name="create_directory",
    description="Create a new directory.",
    tags={"enabled"},
)
def create_directory(path: str, parents: bool = True) -> dict[str, Any]:
    """Create a directory.

    Args:
        path: Path to create.
        parents: Create parent directories if needed.

    Returns:
        dict: Operation status.
    """
    full = safe(path)
    os.makedirs(full, exist_ok=parents)
    logger.info(f"[create_directory] Created directory: {path}")
    return {"ok": True, "path": path}


@mcp.tool(
    name="search_files",
    description="Search for files matching a pattern in a directory tree.",
    tags={"enabled"},
)
def search_files(root: str, pattern: str, max_results: int = 100) -> dict[str, Any]:
    """Search for files matching a pattern.

    Args:
        root: Root directory to search.
        pattern: Glob pattern to match.
        max_results: Maximum number of results.

    Returns:
        dict: List of matching file paths.
    """
    root_full = safe(root)
    if not os.path.exists(root_full):
        logger.error(f"[search_files] Directory not found: {root}")
        return {"ok": False, "error": f"Directory not found: {root}"}

    root_path = Path(root_full)
    matches = list(root_path.glob(pattern))[:max_results]
    results = [{"path": os.path.relpath(m, ROOT), "is_file": m.is_file(), "is_dir": m.is_dir()} for m in matches]

    logger.info(f"[search_files] Found {len(results)} matches for pattern '{pattern}'")
    return {"ok": True, "pattern": pattern, "results": results, "count": len(results)}


@mcp.tool(
    name="exists",
    description="Check if a file or directory exists.",
    tags={"enabled"},
)
def exists(path: str) -> dict[str, Any]:
    """Check if a path exists.

    Args:
        path: Path to check.

    Returns:
        dict: Existence status with type info.
    """
    full = safe(path)
    exists = os.path.exists(full)
    logger.info(f"[exists] Checked existence of {path}: {exists}")
    return {
        "ok": True,
        "path": path,
        "exists": exists,
        "is_file": os.path.isfile(full) if exists else False,
        "is_dir": os.path.isdir(full) if exists else False,
    }


@mcp.tool(
    name="get_size",
    description="Get the total size of a file or directory.",
    tags={"enabled"},
)
def get_size(path: str) -> dict[str, Any]:
    """Get the size of a file or directory.

    Args:
        path: Path to measure.

    Returns:
        dict: Size information.
    """
    full = safe(path)
    if not os.path.exists(full):
        logger.error(f"[get_size] Path not found: {path}")
        return {"ok": False, "error": f"Path not found: {path}"}

    if os.path.isfile(full):
        size = os.path.getsize(full)
    else:
        size = sum(f.stat().st_size for f in Path(full).rglob("*") if f.is_file())

    logger.info(f"[get_size] Got size of {path}: {_format_size(size)}")
    return {
        "ok": True,
        "path": path,
        "size_bytes": size,
        "size_readable": _format_size(size),
    }


@mcp.tool(
    name="get_cwd",
    description="Get current working directory and path information.",
    tags={"enabled"},
)
def get_cwd() -> dict[str, Any]:
    """Get current working directory information.

    Returns:
        dict: Current working directory details.
    """
    logger.info(f"[get_cwd] Retrieved cwd info, root: {ROOT}")
    return {
        "ok": True,
        "root": ROOT,
        "cwd": "",
        "cwd_relative": "",
    }


@mcp.tool(
    name="list_dir",
    description="List contents of a directory.",
    tags={"enabled"},
)
def list_dir(path: str) -> dict[str, Any]:
    """List directory contents.

    Args:
        path: Directory path to list.

    Returns:
        dict: Directory listing with files and directories.
    """
    full = safe(path)
    if not os.path.isdir(full):
        logger.error(f"[list_dir] Not a directory: {path}")
        return {"ok": False, "error": f"Not a directory: {path}"}

    try:
        items = []
        for item in os.listdir(full):
            item_path = os.path.join(full, item)
            is_dir = os.path.isdir(item_path)
            items.append(
                {
                    "name": item,
                    "type": "directory" if is_dir else "file",
                    "size": os.path.getsize(item_path) if not is_dir else None,
                }
            )

        logger.info(f"[list_dir] Listed {len(items)} items in {path}")
        return {
            "ok": True,
            "path": path,
            "items": items,
            "count": len(items),
        }
    except Exception as e:
        logger.error(f"[list_dir] Error listing {path}: {e}")
        return {"ok": False, "error": str(e)}


@mcp.tool(
    name="path_info",
    description="Get information about a path including absolute and relative forms.",
    tags={"enabled"},
)
def path_info(path: str) -> dict[str, Any]:
    """Get path information.

    Args:
        path: Path to analyze.

    Returns:
        dict: Path details including absolute and relative forms.
    """
    full = safe(path)
    p = Path(full)
    logger.info(f"[path_info] Retrieved path info for: {path}")
    return {
        "ok": True,
        "relative_path": path,
        "absolute_path": os.path.abspath(full),
        "parent": os.path.dirname(path),
        "name": p.name,
        "stem": p.stem,
        "extension": p.suffix,
        "is_absolute": os.path.isabs(path),
    }


@mcp.tool(
    name="get_pwd",
    description="Get the current working directory (like Unix pwd command).",
    tags={"enabled"},
)
def get_pwd() -> dict[str, Any]:
    """Get current working directory.

    Returns:
        dict: Current working directory path.
    """
    cwd = os.getcwd()
    logger.info(f"[get_pwd] Current working directory: {cwd}")
    return {"ok": True, "pwd": cwd}


@mcp.tool(
    name="tree",
    description="Display directory tree structure recursively.",
    tags={"enabled"},
)
def tree(path: str = ".", max_depth: int = 3, include_hidden: bool = False) -> dict[str, Any]:
    """Display directory tree structure.

    Args:
        path: Root directory path.
        max_depth: Maximum depth to recurse.
        include_hidden: Whether to include hidden files.

    Returns:
        dict: Tree structure.
    """
    full = safe(path)
    if not os.path.isdir(full):
        logger.error(f"[tree] Not a directory: {path}")
        return {"ok": False, "error": f"Not a directory: {path}"}

    def build_tree(base_path: str, current_depth: int = 0) -> list[dict[str, Any]]:
        if current_depth >= max_depth:
            return []

        items = []
        try:
            for item in os.listdir(base_path):
                if not include_hidden and item.startswith("."):
                    continue

                item_path = os.path.join(base_path, item)
                rel_path = os.path.relpath(item_path, ROOT)
                is_dir = os.path.isdir(item_path)

                entry = {
                    "name": item,
                    "type": "directory" if is_dir else "file",
                    "path": rel_path,
                }
                if is_dir:
                    entry["children"] = build_tree(item_path, current_depth + 1)

                items.append(entry)
        except PermissionError:
            pass

        return sorted(items, key=lambda x: (not x.get("type") == "directory", x["name"]))

    tree_data = {
        "path": path,
        "max_depth": max_depth,
        "tree": build_tree(full),
    }
    logger.info(f"[tree] Generated tree for {path} with max_depth {max_depth}")
    return {"ok": True, **tree_data}


# Health Check
from starlette.requests import Request
from starlette.responses import JSONResponse


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"}, 200)


if __name__ == "__main__":
    logger.info(f"[init] Working directory: {ROOT}")
    try:
        mcp.run(
            transport="streamable-http",
            host=os.getenv("FASTMCP_HOST", "0.0.0.0"),
            port=int(os.getenv("FASTMCP2_PORT", "8005")),
            log_level=os.getenv("FASTMCP_LOG_LEVEL", "INFO"),
            stateless_http=False,
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
