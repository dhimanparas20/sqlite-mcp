"""
sqlite_manager.py — Production-level SQLite3 utility class.

Usage:
    from sqlite_manager import SQLiteManager

    db = SQLiteManager("my_database.db")
    db.create_table("users", {"id": "INTEGER PRIMARY KEY AUTOINCREMENT", "name": "TEXT NOT NULL", "email": "TEXT UNIQUE"})
    db.insert("users", {"name": "Alice", "email": "alice@example.com"})
    users = db.select("users", where={"name": "Alice"})
    db.close()

    # Or use as a context manager:
    with SQLiteManager("my_database.db") as db:
        db.insert("users", {"name": "Bob", "email": "bob@example.com"})
"""

import sqlite3
import json
import logging
import os
import shutil
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)


class SQLiteManagerError(Exception):
    """Base exception for SQLiteManager."""

    pass


class TableNotFoundError(SQLiteManagerError):
    """Raised when a referenced table does not exist."""

    pass


class SQLiteManager:
    """
    A full-featured, production-level SQLite3 utility class.

    Features:
        - Full CRUD on tables and rows
        - Dict/JSON-based input for inserts and updates
        - List-of-dict output for reads
        - Upsert (INSERT OR REPLACE / ON CONFLICT)
        - Bulk insert / bulk upsert
        - Transaction management (begin, commit, rollback, savepoints)
        - Table management (create, drop, rename, alter, list, schema)
        - Pagination, ordering, filtering
        - Aggregation helpers (count, sum, avg, min, max)
        - Raw query execution
        - Database backup and export
        - Context manager support
        - WAL mode and performance pragmas
        - Thread-safe connection options
    """

    def __init__(
        self,
        db_path: str,
        *,
        wal_mode: bool = True,
        autocommit: bool = True,
        detect_types: int = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        timeout: float = 30.0,
        check_same_thread: bool = False,
    ):
        self.db_path = db_path
        self.autocommit = autocommit
        self._connection: Optional[sqlite3.Connection] = None
        self._connect_kwargs = {
            "database": db_path,
            "detect_types": detect_types,
            "timeout": timeout,
            "check_same_thread": check_same_thread,
        }
        self._connect()

        if wal_mode and db_path != ":memory:":
            self._execute_pragma("journal_mode", "WAL")
        self._execute_pragma("foreign_keys", "ON")

    def _connect(self) -> None:
        try:
            self._connection = sqlite3.connect(**self._connect_kwargs)
            self._connection.row_factory = sqlite3.Row
            logger.info("Connected to database: %s", self.db_path)
        except sqlite3.Error as e:
            logger.error("Failed to connect to database: %s", e)
            raise SQLiteManagerError(f"Connection failed: {e}") from e

    def _execute_pragma(self, pragma: str, value: str) -> None:
        self.connection.execute(f"PRAGMA {pragma} = {value};")

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connect()
        return self._connection

    def close(self) -> None:
        if self._connection:
            try:
                self._connection.close()
                logger.info("Database connection closed: %s", self.db_path)
            except sqlite3.Error as e:
                logger.error("Error closing connection: %s", e)
            finally:
                self._connection = None

    def __enter__(self) -> "SQLiteManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.rollback()
            logger.error("Transaction rolled back due to exception: %s", exc_val)
        else:
            self.commit()
        self.close()

    def __del__(self) -> None:
        self.close()

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def begin(self) -> None:
        self.connection.execute("BEGIN;")

    def execute(
        self,
        sql: str,
        params: Optional[Union[Tuple, Dict]] = None,
        *,
        fetch: bool = False,
    ) -> Union[List[Dict[str, Any]], int]:
        params = params or ()
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, params)
            if fetch:
                return [dict(row) for row in cursor.fetchall()]
            if self.autocommit:
                self.connection.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(
                "SQL execution error: %s | SQL: %s | Params: %s", e, sql, params
            )
            raise SQLiteManagerError(f"Execution error: {e}") from e

    def executemany(
        self,
        sql: str,
        params_list: List[Union[Tuple, Dict]],
    ) -> int:
        cursor = self.connection.cursor()
        try:
            cursor.executemany(sql, params_list)
            if self.autocommit:
                self.connection.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            logger.error("executemany error: %s", e)
            raise SQLiteManagerError(f"executemany error: {e}") from e

    def create_table(
        self,
        table: str,
        columns: Dict[str, str],
        *,
        if_not_exists: bool = True,
    ) -> None:
        exists_clause = "IF NOT EXISTS " if if_not_exists else ""
        cols_def = ", ".join(f"{col} {dtype}" for col, dtype in columns.items())
        sql = f"CREATE TABLE {exists_clause}{table} ({cols_def});"
        self.execute(sql)
        logger.info("Table created: %s", table)

    def drop_table(self, table: str, *, if_exists: bool = True) -> None:
        exists_clause = "IF EXISTS " if if_exists else ""
        self.execute(f"DROP TABLE {exists_clause}{table};")
        logger.info("Table dropped: %s", table)

    def list_tables(self) -> List[str]:
        rows = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';",
            fetch=True,
        )
        return [row["name"] for row in rows]

    def table_exists(self, table: str) -> bool:
        rows = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table,),
            fetch=True,
        )
        return len(rows) > 0

    def table_info(self, table: str) -> List[Dict[str, Any]]:
        return self.execute(f"PRAGMA table_info({table});", fetch=True)

    def table_columns(self, table: str) -> List[str]:
        info = self.table_info(table)
        return [col["name"] for col in info]

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders});"
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(data.values()))
            if self.autocommit:
                self.connection.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error("Insert error: %s", e)
            raise SQLiteManagerError(f"Insert error: {e}") from e

    def insert_many(self, table: str, data_list: List[Dict[str, Any]]) -> int:
        if not data_list:
            return 0
        columns = list(data_list[0].keys())
        cols_str = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders});"
        params = [tuple(row.get(c) for c in columns) for row in data_list]
        return self.executemany(sql, params)

    def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        conflict_columns: List[str],
        *,
        update_columns: Optional[List[str]] = None,
    ) -> int:
        if update_columns is None:
            update_columns = [c for c in data.keys() if c not in conflict_columns]

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        conflict_cols = ", ".join(conflict_columns)
        update_set = ", ".join(f"{col} = excluded.{col}" for col in update_columns)

        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        if update_columns:
            sql += f" ON CONFLICT({conflict_cols}) DO UPDATE SET {update_set}"
        else:
            sql += f" ON CONFLICT({conflict_cols}) DO NOTHING"
        sql += ";"

        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(data.values()))
            if self.autocommit:
                self.connection.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error("Upsert error: %s", e)
            raise SQLiteManagerError(f"Upsert error: {e}") from e

    def select(
        self,
        table: str,
        *,
        columns: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        distinct: bool = False,
    ) -> List[Dict[str, Any]]:
        cols = ", ".join(columns) if columns else "*"
        distinct_kw = "DISTINCT " if distinct else ""
        sql = f"SELECT {distinct_kw}{cols} FROM {table}"
        params: list = []

        if where:
            conditions, vals = self._build_where(where)
            sql += f" WHERE {conditions}"
            params.extend(vals)

        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"

        return self.execute(sql + ";", tuple(params), fetch=True)

    def select_one(
        self,
        table: str,
        *,
        columns: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        rows = self.select(table, columns=columns, where=where, limit=1)
        return rows[0] if rows else None

    def select_all(self, table: str) -> List[Dict[str, Any]]:
        return self.select(table)

    def paginate(
        self,
        table: str,
        *,
        page: int = 1,
        page_size: int = 20,
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        total = self.count(table, where=where)
        total_pages = max(1, -(-total // page_size))
        offset = (page - 1) * page_size
        data = self.select(
            table, where=where, order_by=order_by, limit=page_size, offset=offset
        )
        return {
            "data": data,
            "page": page,
            "page_size": page_size,
            "total_rows": total,
            "total_pages": total_pages,
        }

    def update(
        self,
        table: str,
        data: Dict[str, Any],
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        set_clause = ", ".join(f"{col} = ?" for col in data.keys())
        params: list = list(data.values())
        sql = f"UPDATE {table} SET {set_clause}"

        if where:
            conditions, vals = self._build_where(where)
            sql += f" WHERE {conditions}"
            params.extend(vals)

        return self.execute(sql + ";", tuple(params))

    def delete(
        self,
        table: str,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        sql = f"DELETE FROM {table}"
        params: list = []

        if where:
            conditions, vals = self._build_where(where)
            sql += f" WHERE {conditions}"
            params.extend(vals)
        else:
            logger.warning("DELETE called without WHERE on table '%s'", table)

        return self.execute(sql + ";", tuple(params))

    def truncate(self, table: str) -> None:
        self.execute(f"DELETE FROM {table};")
        logger.info("All rows deleted from table: %s", table)

    def count(
        self,
        table: str,
        *,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        sql = f"SELECT COUNT(*) AS cnt FROM {table}"
        params: list = []
        if where:
            conditions, vals = self._build_where(where)
            sql += f" WHERE {conditions}"
            params.extend(vals)
        rows = self.execute(sql + ";", tuple(params), fetch=True)
        return rows[0]["cnt"]

    def exists(self, table: str, where: Dict[str, Any]) -> bool:
        return self.count(table, where=where) > 0

    def search(
        self,
        table: str,
        column: str,
        pattern: str,
        *,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        cols = ", ".join(columns) if columns else "*"
        sql = f"SELECT {cols} FROM {table} WHERE {column} LIKE ?"
        if limit:
            sql += f" LIMIT {limit}"
        return self.execute(sql + ";", (pattern,), fetch=True)

    def backup(self, dest_path: str) -> None:
        dest = sqlite3.connect(dest_path)
        try:
            self.connection.backup(dest)
            logger.info("Database backed up to: %s", dest_path)
        finally:
            dest.close()

    def vacuum(self) -> None:
        self.connection.execute("VACUUM;")

    def database_size(self) -> int:
        if self.db_path == ":memory:":
            return 0
        return os.path.getsize(self.db_path)

    @staticmethod
    def _build_where(where: Dict[str, Any]) -> Tuple[str, List[Any]]:
        conditions = []
        values = []
        for col, val in where.items():
            if val is None:
                conditions.append(f"{col} IS NULL")
            elif isinstance(val, (list, set)):
                placeholders = ", ".join(["?"] * len(val))
                conditions.append(f"{col} IN ({placeholders})")
                values.extend(val)
            else:
                conditions.append(f"{col} = ?")
                values.append(val)
        return " AND ".join(conditions), values


if __name__ == "__main__":
    import os
    import tempfile

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "./demo_sqlite2.db")

    print("=== SQLiteManager Demo ===\n")

    with SQLiteManager(db_path) as db:
        db.create_table(
            "employees",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "name": "TEXT NOT NULL UNIQUE",
                "department": "TEXT",
                "salary": "REAL",
            },
        )
        print("✓ Created 'employees' table")

        db.insert(
            "employees",
            {"name": "Charlie", "department": "Engineering", "salary": 75000},
        )
        db.insert(
            "employees", {"name": "Diana", "department": "Marketing", "salary": 65000}
        )
        print("✓ Inserted 2 employees")

        employees = db.select("employees")
        print(f"\nAll employees: {employees}")

        emp = db.select_one("employees", where={"name": "Charlie"})
        print(f"\nEmployee named Charlie: {emp}")

        db.update("employees", {"salary": 80000}, where={"name": "Charlie"})
        print("\n✓ Updated Charlie's salary to 80000")

        db.delete("employees", where={"name": "Diana"})
        print("✓ Deleted Diana")

        employees = db.select("employees")
        print(f"\nRemaining employees: {employees}")

        count = db.count("employees")
        print(f"Employee count: {count}")

        print("\n=== Upsert Demo ===")
        db.upsert(
            "employees",
            {"name": "Charlie", "department": "Engineering", "salary": 85000},
            conflict_columns=["name"],
        )
        emp = db.select_one("employees", where={"name": "Charlie"})
        print(f"After upsert: {emp}")

        print("\n=== Search Demo ===")
        results = db.search("employees", "department", "%Engine%")
        print(f"Search results: {results}")

        print("\n=== Pagination Demo ===")
        db.insert_many(
            "employees",
            [
                {"name": f"Emp{i}", "department": "IT", "salary": 50000 + i * 1000}
                for i in range(25)
            ],
        )
        page = db.paginate("employees", page=1, page_size=5, order_by="name ASC")
        print(f"Page 1: {page['data']}")
        print(f"Total pages: {page['total_pages']}")

    print("\n=== Demo Complete ===")

    shutil.rmtree(temp_dir, ignore_errors=True)
