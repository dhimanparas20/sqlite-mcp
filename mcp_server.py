from __future__ import annotations

import argparse
import atexit
import importlib.util
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from modules.logger import get_logger

logger = get_logger("[SQLITE]")

_SQLITE1_PATH = Path(__file__).resolve().parent / "modules" / "sqlite3" / "sqlite_1.py"
_SQLITE1_SPEC = importlib.util.spec_from_file_location("sqlite_1_local", _SQLITE1_PATH)
if _SQLITE1_SPEC is None or _SQLITE1_SPEC.loader is None:
    raise RuntimeError(f"Unable to load sqlite helper module from {_SQLITE1_PATH}")
_SQLITE1_MODULE = importlib.util.module_from_spec(_SQLITE1_SPEC)
_SQLITE1_SPEC.loader.exec_module(_SQLITE1_MODULE)
SQLiteUtils = _SQLITE1_MODULE.SQLiteUtils


DEFAULT_DB_PATH = os.getenv(
    "SQLITE_MCP_DB_PATH",
    str(Path(__file__).resolve().parent / "sqlite_ops.db"),
)

sqlite_db = SQLiteUtils(DEFAULT_DB_PATH)
atexit.register(sqlite_db.close)

mcp = FastMCP(name="SQLite3 Ops.", tasks=False)


def _commit() -> None:
    sqlite_db.connection.commit()
    logger.info("[SQLITE] transaction committed")


def _rollback(error: Exception) -> None:
    sqlite_db.connection.rollback()
    logger.error(f"[SQLITE] transaction rolled back: {error}")


def _set_db_path(db_path: str) -> None:
    global sqlite_db
    sqlite_db.close()
    sqlite_db = SQLiteUtils(db_path)
    logger.info(f"[SQLITE] active database path set to: {db_path}")


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
    tables = sqlite_db.list_tables()
    logger.info(f"[list_tables] listed {len(tables)} table(s)")
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
    info = sqlite_db.get_table_info(table_name)
    payload = asdict(info) if info else None
    logger.info(
        f"[table_info] loaded schema for table={table_name!r}, exists={payload is not None}"
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
    if columns is None:
        logger.error("[create_table] error: columns parameter is required")
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
        _commit()
        logger.info(f"[create_table] table created or already exists: {table_name!r}")
        return {"ok": True, "table": table_name}
    except Exception as error:
        _rollback(error)
        logger.error(f"[create_table] error creating table: {error}")
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
    try:
        result = sqlite_db.insert(table_name, data)
        _commit()
        if isinstance(result, list):
            logger.info(
                f"[insert_rows] inserted {len(result)} row(s) into {table_name!r}"
            )
            return {"rows_inserted": len(result), "row_ids": result}
        logger.info(f"[insert_rows] inserted 1 row into {table_name!r}")
        return {"rows_inserted": 1, "row_id": result}
    except Exception as error:
        _rollback(error)
        logger.error(f"[insert_rows] error inserting rows: {error}")
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
    rows = sqlite_db.select(
        table_name=table_name,
        columns=columns,
        where=where,
        order_by=order_by,
        limit=limit,
        offset=offset,
        distinct=distinct,
    )
    logger.info(f"[select_rows] selected {len(rows)} row(s) from {table_name!r}")
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
    row = sqlite_db.select_one(
        table_name=table_name,
        columns=columns,
        where=where,
        order_by=order_by,
    )
    logger.info(
        f"[select_one_row] selected one from {table_name!r}, found={row is not None}"
    )
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
    try:
        rowcount = sqlite_db.update(
            table_name=table_name, data=data, where=where if where else {}
        )
        _commit()
        logger.info(f"[update_rows] updated {rowcount} row(s) in {table_name!r}")
        return {"ok": True, "rows_updated": rowcount}
    except Exception as error:
        _rollback(error)
        logger.error(f"[update_rows] error updating rows: {error}")
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
    try:
        rowcount = sqlite_db.delete(table_name=table_name, where=where if where else {})
        _commit()
        logger.info(f"[delete_rows] deleted {rowcount} row(s) from {table_name!r}")
        return {"ok": True, "rows_deleted": rowcount}
    except Exception as error:
        _rollback(error)
        logger.error(f"[delete_rows] error deleting rows: {error}")
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
    try:
        rowcount = sqlite_db.upsert(
            table_name=table_name,
            data=data,
            conflict_columns=conflict_columns,
            update_columns=update_columns,
        )
        _commit()
        logger.info(f"[upsert_row] upsert affected {rowcount} row(s) in {table_name!r}")
        return {"ok": True, "rows_affected": rowcount}
    except Exception as error:
        _rollback(error)
        logger.error(f"[upsert_row] error upserting row: {error}")
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
    total = sqlite_db.count(table_name=table_name, where=where)
    logger.info(f"[count_rows] counted rows in {table_name!r}: {total}")
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
    db_path = str(sqlite_db.db_path)
    logger.info(f"[active_database] active database path: {db_path}")
    return {"db_path": db_path}


@mcp.tool(
    name="delete_table",
    description="Delete (drop) a specific table from the database.",
    tags={"enabled"},
)
async def delete_table(table_name: str) -> dict[str, Any]:
    """Drop a table from the active database.

    Args:
        table_name (str): Name of the table to drop.

    Returns:
        dict[str, Any]: Operation status with table name.
    """
    try:
        cursor = sqlite_db.connection.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        _commit()
        logger.info(f"[delete_table] dropped table: {table_name!r}")
        return {"ok": True, "table": table_name}
    except Exception as error:
        _rollback(error)
        logger.error(f"[delete_table] error dropping table: {error}")
        return {"ok": False, "error": str(error), "table": table_name}


@mcp.tool(
    name="flush_database",
    description="Delete all tables from the database, effectively flushing all data.",
    tags={"enabled"},
)
async def flush_database() -> dict[str, Any]:
    """Drop all tables from the active database.

    Returns:
        dict[str, Any]: Operation status with list of dropped tables.
    """
    try:
        tables = sqlite_db.list_tables()
        cursor = sqlite_db.connection.cursor()
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        _commit()
        logger.info(f"[flush_database] flushed {len(tables)} table(s)")
        return {"ok": True, "tables_dropped": tables, "count": len(tables)}
    except Exception as error:
        _rollback(error)
        logger.error(f"[flush_database] error flushing database: {error}")
        return {"ok": False, "error": str(error)}


@mcp.tool(
    name="rename_table",
    description="Rename a table in the database.",
    tags={"enabled"},
)
async def rename_table(table_name: str, new_table_name: str) -> dict[str, Any]:
    """Rename a table in the active database.

    Args:
        table_name (str): Current name of the table.
        new_table_name (str): New name for the table.

    Returns:
        dict[str, Any]: Operation status with old and new table names.
    """
    try:
        cursor = sqlite_db.connection.cursor()
        cursor.execute(f"ALTER TABLE {table_name} RENAME TO {new_table_name}")
        _commit()
        logger.info(
            f"[rename_table] renamed table {table_name!r} to {new_table_name!r}"
        )
        return {"ok": True, "old_name": table_name, "new_name": new_table_name}
    except Exception as error:
        _rollback(error)
        logger.error(f"[rename_table] error renaming table: {error}")
        return {"ok": False, "error": str(error), "table": table_name}


@mcp.tool(
    name="execute_sql",
    description="Execute raw SQL query against the database.",
    tags={"enabled"},
)
async def execute_sql(sql: str, params: list | None = None) -> dict[str, Any]:
    """Execute raw SQL query.

    Args:
        sql (str): SQL query to execute.
        params (list | None): Optional query parameters.

    Returns:
        dict[str, Any]: Query results or affected row count.
    """
    try:
        cursor = sqlite_db.connection.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        if sql.strip().upper().startswith(("SELECT", "PRAGMA", "EXPLAIN")):
            columns = (
                [desc[0] for desc in cursor.description] if cursor.description else []
            )
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            logger.info(f"[execute_sql] executed query, returned {len(rows)} rows")
            return {
                "ok": True,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
        else:
            rowcount = cursor.rowcount
            _commit()
            logger.info(f"[execute_sql] executed statement, affected {rowcount} rows")
            return {"ok": True, "affected_rows": rowcount}
    except Exception as error:
        _rollback(error)
        logger.error(f"[execute_sql] error executing SQL: {error}")
        return {"ok": False, "error": str(error)}


@mcp.tool(
    name="create_index",
    description="Create an index on a table column.",
    tags={"enabled"},
)
async def create_index(
    index_name: str,
    table_name: str,
    columns: list[str],
    unique: bool = False,
    if_not_exists: bool = True,
) -> dict[str, Any]:
    """Create an index on a table.

    Args:
        index_name (str): Name for the index.
        table_name (str): Table to index.
        columns (list[str]): Columns to include in the index.
        unique (bool): Whether to create a unique index.
        if_not_exists (bool): Use IF NOT EXISTS clause.

    Returns:
        dict[str, Any]: Operation status.
    """
    try:
        unique_str = "UNIQUE " if unique else ""
        if_not_exists_str = "IF NOT EXISTS " if if_not_exists else ""
        columns_str = ", ".join(columns)
        sql = f"CREATE {unique_str}INDEX {if_not_exists_str}{index_name} ON {table_name} ({columns_str})"

        cursor = sqlite_db.connection.cursor()
        cursor.execute(sql)
        _commit()

        logger.info(
            f"[create_index] created index {index_name} on {table_name}({columns_str})"
        )
        return {
            "ok": True,
            "index": index_name,
            "table": table_name,
            "columns": columns,
        }
    except Exception as error:
        _rollback(error)
        logger.error(f"[create_index] error creating index: {error}")
        return {"ok": False, "error": str(error)}


@mcp.tool(
    name="list_indexes",
    description="List all indexes in the database.",
    tags={"enabled"},
)
async def list_indexes() -> dict[str, Any]:
    """List all indexes in the database.

    Returns:
        dict[str, Any]: List of indexes with details.
    """
    try:
        cursor = sqlite_db.connection.cursor()
        cursor.execute("""
            SELECT name, tbl_name, sql 
            FROM sqlite_master 
            WHERE type = 'index' AND sql IS NOT NULL
            ORDER BY tbl_name, name
        """)
        indexes = [
            {"name": row[0], "table": row[1], "sql": row[2]}
            for row in cursor.fetchall()
        ]

        logger.info(f"[list_indexes] listed {len(indexes)} indexes")
        return {"ok": True, "indexes": indexes, "count": len(indexes)}
    except Exception as error:
        logger.error(f"[list_indexes] error listing indexes: {error}")
        return {"ok": False, "error": str(error)}


@mcp.tool(
    name="vacuum_database",
    description="Optimize the database by reclaiming space.",
    tags={"enabled"},
)
async def vacuum_database() -> dict[str, Any]:
    """Vacuum the database to optimize storage.

    Returns:
        dict[str, Any]: Operation status.
    """
    try:
        cursor = sqlite_db.connection.cursor()
        cursor.execute("VACUUM")
        logger.info("[vacuum_database] database vacuumed successfully")
        return {"ok": True, "message": "Database vacuumed successfully"}
    except Exception as error:
        logger.error(f"[vacuum_database] error vacuuming: {error}")
        return {"ok": False, "error": str(error)}


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
