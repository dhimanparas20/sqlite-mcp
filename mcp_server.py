from __future__ import annotations

import argparse
import atexit
import importlib.util
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

_SQLITE1_PATH = Path(__file__).resolve().parent / "modules" / "sqlite3" / "sqlite_1.py"
_SQLITE1_SPEC = importlib.util.spec_from_file_location("sqlite_1_local", _SQLITE1_PATH)
if _SQLITE1_SPEC is None or _SQLITE1_SPEC.loader is None:
    raise RuntimeError(f"Unable to load sqlite helper module from {_SQLITE1_PATH}")
_SQLITE1_MODULE = importlib.util.module_from_spec(_SQLITE1_SPEC)
_SQLITE1_SPEC.loader.exec_module(_SQLITE1_MODULE)
SQLiteUtils = _SQLITE1_MODULE.SQLiteUtils

try:
    from loguru import logger
except ImportError:
    import logging

    _fallback_logger = logging.getLogger("sqlite-mcp")
    _fallback_logger.setLevel(logging.INFO)
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _fallback_logger.handlers = [_handler]

    class _LoggerProxy:
        def __init__(self, method: str = "global") -> None:
            self._method = method

        def remove(self) -> None:
            return None

        def add(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def bind(self, **kwargs: Any) -> "_LoggerProxy":
            return _LoggerProxy(method=kwargs.get("method", "global"))

        def log(self, _level: str, message: str) -> None:
            _fallback_logger.info(message)

    logger = _LoggerProxy()


DEFAULT_DB_PATH = os.getenv(
    "SQLITE_MCP_DB_PATH",
    str(Path(__file__).resolve().parent / "sqlite_ops.db"),
)
LOG_SOURCE_NAME = Path(__file__).name

logger.remove()
logger.add(
    sys.stderr,
    format=f"[{LOG_SOURCE_NAME}][{{extra[method]}}] {{message}}",
    level="INFO",
)

sqlite_db = SQLiteUtils(DEFAULT_DB_PATH)
atexit.register(sqlite_db.close)

mcp = FastMCP(name="SQLite3 Ops.", tasks=False)


def _log(method_name: str, message: str, level: str = "INFO") -> None:
    logger.bind(method=method_name).log(level.upper(), message)


def _commit(method_name: str) -> None:
    sqlite_db.connection.commit()
    _log(method_name, "transaction committed")


def _rollback(method_name: str, error: Exception) -> None:
    sqlite_db.connection.rollback()
    _log(method_name, f"transaction rolled back: {error}", "ERROR")


def _set_db_path(db_path: str) -> None:
    global sqlite_db
    sqlite_db.close()
    sqlite_db = SQLiteUtils(db_path)
    _log("set_db_path", f"active database path set to: {db_path}")


@mcp.tool(
    name="list_tables",
    description="List all tables in the configured SQLite database.",
    tags={"enabled"},
)
async def list_tables() -> list[str]:
    """List all table names from the active database.

    Returns:
        list[str]: Table names sorted by SQLite query order.
    """
    method_name = "list_tables"
    tables = sqlite_db.list_tables()
    _log(method_name, f"listed {len(tables)} table(s)")
    return tables


@mcp.tool(
    name="table_info",
    description="Get schema information for a specific table.",
    tags={"enabled"},
)
async def table_info(table_name: str) -> dict[str, Any] | None:
    """Fetch schema metadata for a single table.

    Args:
        table_name (str): The table to inspect.

    Returns:
        dict[str, Any] | None: Dataclass payload as dict if table exists, else None.
    """
    method_name = "table_info"
    info = sqlite_db.get_table_info(table_name)
    payload = asdict(info) if info else None
    _log(
        method_name,
        f"loaded schema for table={table_name!r}, exists={payload is not None}",
    )
    return payload


@mcp.tool(
    name="create_table",
    description="Create a table with optional primary key and unique constraint.",
    tags={"enabled"},
)
async def create_table(
    table_name: str,
    columns: dict[str, str] | None = None,
    if_not_exists: bool = True,
    primary_key: str | None = None,
    unique: list[str] | None = None,
) -> dict[str, Any]:
    """Create a table in the active database.

    Args:
        table_name (str): Destination table name.
        columns (dict[str, str] | None): Mapping of column name to SQL type definition.
        if_not_exists (bool): Whether to include IF NOT EXISTS.
        primary_key (str | None): Optional primary key column name.
        unique (list[str] | None): Optional unique constraint columns.

    Returns:
        dict[str, Any]: Operation status with created table name or error message.
    """
    method_name = "create_table"

    if columns is None:
        _log(method_name, "error: columns parameter is required", "ERROR")
        return {
            "ok": False,
            "error": "Missing required parameter: columns (dict of column names to SQL types)",
            "table": table_name,
        }

    try:
        sqlite_db.create_table(
            table_name=table_name,
            columns=columns,
            if_not_exists=if_not_exists,
            primary_key=primary_key,
            unique=unique,
        )
        _commit(method_name)
        _log(method_name, f"table created or already exists: {table_name!r}")
        return {"ok": True, "table": table_name}
    except Exception as error:
        _rollback(method_name, error)
        _log(method_name, f"error creating table: {error}", "ERROR")
        return {"ok": False, "error": str(error), "table": table_name}


@mcp.tool(
    name="insert_rows",
    description="Insert one or more rows into a table.",
    tags={"enabled"},
)
async def insert_rows(
    data: dict[str, Any] | list[dict[str, Any]], table_name: str
) -> dict[str, Any]:
    """Insert rows into a table.

    Args:
        data (dict[str, Any] | list[dict[str, Any]]): Row object or list of row objects.
        table_name (str): Target table name.

    Returns:
        dict[str, Any]: Insert metadata including affected rows and row ids.
    """
    method_name = "insert_rows"
    try:
        result = sqlite_db.insert(table_name, data)
        _commit(method_name)
        if isinstance(result, list):
            _log(method_name, f"inserted {len(result)} row(s) into {table_name!r}")
            return {"rows_inserted": len(result), "row_ids": result}
        _log(method_name, f"inserted 1 row into {table_name!r}")
        return {"rows_inserted": 1, "row_id": result}
    except Exception as error:
        _rollback(method_name, error)
        _log(method_name, f"error inserting rows: {error}", "ERROR")
        return {"ok": False, "error": str(error), "table": table_name}


@mcp.tool(
    name="select_rows",
    description="Select rows from a table with optional filters and pagination.",
    tags={"enabled"},
)
async def select_rows(
    table_name: str,
    columns: list[str] | None = None,
    where: dict[str, Any] | None = None,
    order_by: dict[str, str] | None = None,
    limit: int | None = None,
    offset: int | None = None,
    distinct: bool = False,
) -> list[dict[str, Any]]:
    """Select rows from a table.

    Args:
        table_name (str): Source table name.
        columns (list[str] | None): Optional column projection.
        where (dict[str, Any] | None): Optional equality predicates.
        order_by (dict[str, str] | None): Optional column sort map, e.g. {"id": "DESC"}.
        limit (int | None): Maximum rows to return.
        offset (int | None): Row offset for pagination.
        distinct (bool): Whether to use DISTINCT.

    Returns:
        list[dict[str, Any]]: Matching rows.
    """
    method_name = "select_rows"
    rows = sqlite_db.select(
        table_name=table_name,
        columns=columns,
        where=where,
        order_by=order_by,
        limit=limit,
        offset=offset,
        distinct=distinct,
    )
    _log(method_name, f"selected {len(rows)} row(s) from {table_name!r}")
    return rows


@mcp.tool(
    name="select_one_row",
    description="Select the first row matching optional filters.",
    tags={"enabled"},
)
async def select_one_row(
    table_name: str,
    columns: list[str] | None = None,
    where: dict[str, Any] | None = None,
    order_by: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Select one row from a table.

    Args:
        table_name (str): Source table name.
        columns (list[str] | None): Optional column projection.
        where (dict[str, Any] | None): Optional equality predicates.
        order_by (dict[str, str] | None): Optional ordering before first row selection.

    Returns:
        dict[str, Any] | None: First matching row, else None.
    """
    method_name = "select_one_row"
    row = sqlite_db.select_one(
        table_name=table_name,
        columns=columns,
        where=where,
        order_by=order_by,
    )
    _log(method_name, f"selected one from {table_name!r}, found={row is not None}")
    return row


@mcp.tool(
    name="update_rows",
    description="Update rows in a table using data and where predicates.",
    tags={"enabled"},
)
async def update_rows(
    table_name: str, data: dict[str, Any], where: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Update rows matching WHERE criteria.

    Args:
        table_name (str): Target table name.
        data (dict[str, Any]): Columns and values to update.
        where (dict[str, Any] | None): Equality predicates for row selection.

    Returns:
        dict[str, Any]: Number of rows updated.
    """
    method_name = "update_rows"
    try:
        rowcount = sqlite_db.update(
            table_name=table_name, data=data, where=where if where else {}
        )
        _commit(method_name)
        _log(method_name, f"updated {rowcount} row(s) in {table_name!r}")
        return {"ok": True, "rows_updated": rowcount}
    except Exception as error:
        _rollback(method_name, error)
        _log(method_name, f"error updating rows: {error}", "ERROR")
        return {"ok": False, "error": str(error), "table": table_name}


@mcp.tool(
    name="delete_rows",
    description="Delete rows from a table using where predicates.",
    tags={"enabled"},
)
async def delete_rows(
    table_name: str, where: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Delete rows matching WHERE criteria.

    Args:
        table_name (str): Target table name.
        where (dict[str, Any] | None): Equality predicates for row deletion.

    Returns:
        dict[str, Any]: Number of rows deleted.
    """
    method_name = "delete_rows"
    try:
        rowcount = sqlite_db.delete(table_name=table_name, where=where if where else {})
        _commit(method_name)
        _log(method_name, f"deleted {rowcount} row(s) from {table_name!r}")
        return {"ok": True, "rows_deleted": rowcount}
    except Exception as error:
        _rollback(method_name, error)
        _log(method_name, f"error deleting rows: {error}", "ERROR")
        return {"ok": False, "error": str(error), "table": table_name}


@mcp.tool(
    name="upsert_row",
    description="Upsert a row using conflict columns and optional update columns.",
    tags={"enabled"},
)
async def upsert_row(
    table_name: str,
    data: dict[str, Any],
    conflict_columns: list[str],
    update_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Insert or update a row on conflict.

    Args:
        table_name (str): Target table name.
        data (dict[str, Any]): Row payload.
        conflict_columns (list[str]): ON CONFLICT column set.
        update_columns (list[str] | None): Optional subset of columns to update.

    Returns:
        dict[str, Any]: Number of affected rows.
    """
    method_name = "upsert_row"
    try:
        rowcount = sqlite_db.upsert(
            table_name=table_name,
            data=data,
            conflict_columns=conflict_columns,
            update_columns=update_columns,
        )
        _commit(method_name)
        _log(method_name, f"upsert affected {rowcount} row(s) in {table_name!r}")
        return {"ok": True, "rows_affected": rowcount}
    except Exception as error:
        _rollback(method_name, error)
        _log(method_name, f"error upserting row: {error}", "ERROR")
        return {"ok": False, "error": str(error), "table": table_name}


@mcp.tool(
    name="count_rows",
    description="Count rows in a table with optional where predicates.",
    tags={"enabled"},
)
async def count_rows(
    table_name: str, where: dict[str, Any] | None = None
) -> dict[str, int]:
    """Count rows in a table.

    Args:
        table_name (str): Target table name.
        where (dict[str, Any] | None): Optional equality predicates.

    Returns:
        dict[str, int]: Total row count.
    """
    method_name = "count_rows"
    total = sqlite_db.count(table_name=table_name, where=where)
    _log(method_name, f"counted rows in {table_name!r}: {total}")
    return {"count": total}


@mcp.tool(
    name="active_database",
    description="Get the currently configured SQLite database file path.",
    tags={"enabled"},
)
async def active_database() -> dict[str, str]:
    """Return the active database file path for this server process.

    Returns:
        dict[str, str]: Active `db_path` value.
    """
    method_name = "active_database"
    db_path = str(sqlite_db.db_path)
    _log(method_name, f"active database path: {db_path}")
    return {"db_path": db_path}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQLite FastMCP server")
    parser.add_argument("--host", default=os.getenv("FASTMCP_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("FASTMCP_PORT", "8000"))
    )
    parser.add_argument(
        "--path",
        default=os.getenv("FASTMCP_STREAMABLE_HTTP_PATH", "/mcp"),
        help="Streamable HTTP endpoint path.",
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="SQLite database file path used by the global SQLiteUtils instance.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    _set_db_path(args.db_path)
    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        path=args.path,
        log_level="INFO",
        stateless_http=False,
    )
