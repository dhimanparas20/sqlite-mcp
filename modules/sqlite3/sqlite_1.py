"""
SQLite3 Utility Class - Production Level
A full-featured SQLite3 wrapper for CRUD operations with JSON/dict support.
"""

import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
from contextlib import contextmanager
from loguru import logger

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}", level="DEBUG")


@dataclass
class TableInfo:
    name: str
    columns: List[Dict[str, str]]
    primary_key: Optional[str] = None


class SQLiteUtils:
    """
    Production-level SQLite3 utility class for database operations.

    Features:
    - Full CRUD operations on tables and rows
    - JSON/dict input for create/update operations
    - Returns list of dicts/objects for read operations
    - Upsert support (INSERT OR REPLACE/IGNORE)
    - Transaction management
    - Table introspection
    - Connection pooling
    """

    def __init__(
        self,
        db_path: Union[str, Path],
        timeout: float = 30.0,
        check_same_thread: bool = False,
    ):
        """
        Initialize SQLiteUtils.

        Args:
            db_path: Path to SQLite database file
            timeout: Connection timeout in seconds
            check_same_thread: Allow multi-threaded access
        """
        self.db_path = Path(db_path)
        self.timeout = timeout
        self.check_same_thread = check_same_thread
        self._connection: Optional[sqlite3.Connection] = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create connection with auto-commit disabled for transactions."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                timeout=self.timeout,
                check_same_thread=self.check_same_thread,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    @contextmanager
    def transaction(self):
        """Context manager for transactions."""
        conn = self.connection
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise

    def close(self):
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def execute(self, query: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return cursor."""
        return self.connection.execute(query, params)

    def executemany(self, query: str, params: List[Tuple]) -> sqlite3.Cursor:
        """Execute a query with multiple parameter sets."""
        return self.connection.executemany(query, params)

    def fetchone(self, query: str, params: Tuple = ()) -> Optional[Dict]:
        """Execute query and fetch one result as dict."""
        cursor = self.connection.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self, query: str, params: Tuple = ()) -> List[Dict]:
        """Execute query and fetch all results as list of dicts."""
        cursor = self.connection.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def create_table(
        self,
        table_name: str,
        columns: Dict[str, str],
        if_not_exists: bool = True,
        primary_key: Optional[str] = None,
        foreign_keys: Optional[Dict[str, Tuple[str, str, str]]] = None,
        unique: Optional[List[str]] = None,
    ) -> bool:
        """
        Create a table with specified columns.

        Args:
            table_name: Name of the table
            columns: Dict of {column_name: sql_type} (e.g., {"id": "INTEGER", "name": "TEXT"})
            if_not_exists: Use IF NOT EXISTS clause
            primary_key: Primary key column name
            foreign_keys: Dict of {column: (ref_table, ref_column, on_delete)}
            unique: List of column names that should be unique

        Returns:
            True if successful
        """
        exists_clause = "IF NOT EXISTS " if if_not_exists else ""
        cols = []

        for col_name, col_type in columns.items():
            col_def = f"{col_name} {col_type}"
            if primary_key and col_name == primary_key:
                col_def += " PRIMARY KEY"
            cols.append(col_def)

        if unique:
            cols.append(f"UNIQUE({', '.join(unique)})")

        if foreign_keys:
            for col, (ref_table, ref_col, on_delete) in foreign_keys.items():
                cols.append(
                    f"FOREIGN KEY ({col}) REFERENCES {ref_table}({ref_col}) ON DELETE {on_delete}"
                )

        query = f"CREATE TABLE {exists_clause}{table_name} ({', '.join(cols)})"
        self.execute(query)
        self.connection.commit()
        return True

    def drop_table(self, table_name: str, if_exists: bool = True) -> bool:
        """Drop a table."""
        exists_clause = "IF EXISTS " if if_exists else ""
        self.execute(f"DROP TABLE {exists_clause}{table_name}")
        self.connection.commit()
        return True

    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.fetchone(query, (table_name,))
        return result is not None

    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """Get table schema information."""
        if not self.table_exists(table_name):
            return None

        cursor = self.connection.execute(f"PRAGMA table_info({table_name})")
        columns = []
        primary_key = None

        for row in cursor.fetchall():
            col_info = {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": row["notnull"],
                "default_value": row["dflt_value"],
                "pk": row["pk"],
            }
            columns.append(col_info)
            if row["pk"]:
                primary_key = row["name"]

        return TableInfo(name=table_name, columns=columns, primary_key=primary_key)

    def list_tables(self) -> List[str]:
        """List all tables in the database."""
        query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        return [row["name"] for row in self.fetchall(query)]

    def insert(
        self, table_name: str, data: Union[Dict, List[Dict]]
    ) -> Union[int, List[int]]:
        """
        Insert a single row or multiple rows.

        Args:
            table_name: Table name
            data: Dict for single row or list of dicts for multiple rows

        Returns:
            Row ID for single insert, list of row IDs for bulk insert
        """
        if isinstance(data, dict):
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?" for _ in data])
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            cursor = self.execute(query, tuple(data.values()))
            return cursor.lastrowid
        else:
            if not data:
                return []
            columns = ", ".join(data[0].keys())
            placeholders = ", ".join(["?" for _ in data[0]])
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            params = [tuple(row.values()) for row in data]
            self.executemany(query, params)
            self.connection.commit()
            cursor = self.execute("SELECT last_insert_rowid()")
            start_id = cursor.fetchone()[0]
            return list(range(start_id, start_id + len(data)))

    def insert_or_ignore(self, table_name: str, data: Union[Dict, List[Dict]]) -> int:
        """Insert rows, ignoring duplicates (INSERT OR IGNORE)."""
        if isinstance(data, dict):
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?" for _ in data])
            query = f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})"
            cursor = self.execute(query, tuple(data.values()))
            return cursor.rowcount
        else:
            columns = ", ".join(data[0].keys())
            placeholders = ", ".join(["?" for _ in data[0]])
            query = f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})"
            params = [tuple(row.values()) for row in data]
            self.executemany(query, params)
            self.connection.commit()
            return len(data)

    def upsert(
        self,
        table_name: str,
        data: Dict,
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None,
    ) -> int:
        """
        Insert a row or replace on conflict (UPSERT).

        Args:
            table_name: Table name
            data: Dict of data to insert/update
            conflict_columns: Columns to check for conflict (for ON CONFLICT)
            update_columns: Columns to update on conflict (if None, updates all non-PK columns)

        Returns:
            Number of rows affected
        """
        columns = list(data.keys())
        col_str = ", ".join(columns)
        placeholders = ", ".join(["?" for _ in data])

        if update_columns is None:
            update_columns = [c for c in columns if c not in conflict_columns]

        update_str = ", ".join([f"{c} = excluded.{c}" for c in update_columns])
        conflict_str = ", ".join(conflict_columns)

        query = f"""
        INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})
        ON CONFLICT({conflict_str}) DO UPDATE SET {update_str}
        """
        cursor = self.execute(query, tuple(data.values()))
        return cursor.rowcount

    def replace(
        self, table_name: str, data: Union[Dict, List[Dict]]
    ) -> Union[int, List[int]]:
        """Replace rows (insert or replace)."""
        if isinstance(data, dict):
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?" for _ in data])
            query = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
            cursor = self.execute(query, tuple(data.values()))
            return cursor.lastrowid
        else:
            columns = ", ".join(data[0].keys())
            placeholders = ", ".join(["?" for _ in data[0]])
            query = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
            params = [tuple(row.values()) for row in data]
            self.executemany(query, params)
            self.connection.commit()
            return [i + 1 for i in range(len(data))]

    def _build_where_clause(self, where: Dict) -> Tuple[str, Tuple]:
        if not where:
            return "", ()

        conditions = []
        params = []

        for key, value in where.items():
            if "__gt" in key:
                col = key.replace("__gt", "")
                conditions.append(f"{col} > ?")
                params.append(value)
            elif "__lt" in key:
                col = key.replace("__lt", "")
                conditions.append(f"{col} < ?")
                params.append(value)
            elif "__gte" in key:
                col = key.replace("__gte", "")
                conditions.append(f"{col} >= ?")
                params.append(value)
            elif "__lte" in key:
                col = key.replace("__lte", "")
                conditions.append(f"{col} <= ?")
                params.append(value)
            elif "__ne" in key:
                col = key.replace("__ne", "")
                conditions.append(f"{col} != ?")
                params.append(value)
            else:
                conditions.append(f"{key} = ?")
                params.append(value)

        return " AND ".join(conditions), tuple(params)

    def select(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        where: Optional[Dict] = None,
        order_by: Optional[Dict] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        group_by: Optional[str] = None,
        having: Optional[str] = None,
        join: Optional[Dict] = None,
        distinct: bool = False,
    ) -> List[Dict]:
        """
        Select rows from table with flexible filtering.

        Args:
            table_name: Table name
            columns: Columns to select (default: all)
            where: Dict of {column: value} for WHERE clause
            order_by: Dict of {column: "ASC"|"DESC"}
            limit: Limit number of results
            offset: Offset for pagination
            group_by: GROUP BY clause
            having: HAVING clause
            join: Dict of {table: {type: "INNER"|"LEFT", on: "condition"}}
            distinct: Add DISTINCT keyword

        Returns:
            List of dicts representing rows
        """
        col_str = "*" if columns is None else ", ".join(columns)
        distinct_str = "DISTINCT " if distinct else ""

        query = f"SELECT {distinct_str}{col_str} FROM {table_name}"

        if join:
            for j_table, j_info in join.items():
                j_type = j_info.get("type", "INNER")
                query += f" {j_type} JOIN {j_table} ON {j_info['on']}"

        if where:
            conditions, params = self._build_where_clause(where)
            if conditions:
                query += f" WHERE {conditions}"
        else:
            params = ()

        if group_by:
            query += f" GROUP BY {group_by}"
            if having:
                query += f" HAVING {having}"

        if order_by:
            order_parts = [f"{k} {v}" for k, v in order_by.items()]
            query += f" ORDER BY {', '.join(order_parts)}"

        if limit is not None:
            query += f" LIMIT {limit}"
        if offset is not None:
            query += f" OFFSET {offset}"

        return self.fetchall(query, params)

    def select_one(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        where: Optional[Dict] = None,
        order_by: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """Select a single row."""
        results = self.select(table_name, columns, where, order_by, limit=1)
        return results[0] if results else None

    def select_raw(self, query: str, params: Tuple = ()) -> List[Dict]:
        """Execute raw SELECT query."""
        return self.fetchall(query, params)

    def select_one_raw(self, query: str, params: Tuple = ()) -> Optional[Dict]:
        """Execute raw SELECT query and return one result."""
        return self.fetchone(query, params)

    def update(self, table_name: str, data: Dict, where: Dict) -> int:
        """
        Update rows matching WHERE criteria.

        Args:
            table_name: Table name
            data: Dict of {column: new_value}
            where: Dict of {column: value} for WHERE clause

        Returns:
            Number of rows affected
        """
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])

        if where:
            conditions, where_params = self._build_where_clause(where)
            where_clause = conditions
            params = tuple(list(data.values()) + list(where_params))
        else:
            where_clause = "1=1"
            params = tuple(data.values())

        query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"

        cursor = self.execute(query, params)
        self.connection.commit()
        return cursor.rowcount

    def delete(self, table_name: str, where: Dict) -> int:
        """
        Delete rows matching WHERE criteria.

        Args:
            table_name: Table name
            where: Dict of {column: value} for WHERE clause

        Returns:
            Number of rows deleted
        """
        if where:
            conditions, params = self._build_where_clause(where)
            where_clause = conditions
        else:
            where_clause = "1=1"
            params = ()

        query = f"DELETE FROM {table_name} WHERE {where_clause}"

        cursor = self.execute(query, params)
        self.connection.commit()
        return cursor.rowcount

    def delete_by_id(
        self, table_name: str, id_value: Any, id_column: str = "id"
    ) -> int:
        """Delete a row by its primary key."""
        return self.delete(table_name, {id_column: id_value})

    def count(self, table_name: str, where: Optional[Dict] = None) -> int:
        """Count rows in table with optional WHERE clause."""
        query = f"SELECT COUNT(*) as count FROM {table_name}"

        if where:
            conditions, params = self._build_where_clause(where)
            if conditions:
                query += f" WHERE {conditions}"
        else:
            params = ()

        result = self.fetchone(query, params)
        return result["count"] if result else 0

    def exists(self, table_name: str, where: Dict) -> bool:
        """Check if a row exists matching the criteria."""
        query = f"SELECT 1 FROM {table_name} WHERE {' AND '.join([f'{k} = ?' for k in where.keys()])} LIMIT 1"
        return self.fetchone(query, tuple(where.values())) is not None

    def max(
        self, table_name: str, column: str, where: Optional[Dict] = None
    ) -> Optional[Any]:
        """Get max value of a column."""
        query = f"SELECT MAX({column}) as max_val FROM {table_name}"
        params = ()

        if where:
            conditions = " AND ".join([f"{k} = ?" for k in where.keys()])
            query += f" WHERE {conditions}"
            params = tuple(where.values())

        result = self.fetchone(query, params)
        return result["max_val"] if result else None

    def min(
        self, table_name: str, column: str, where: Optional[Dict] = None
    ) -> Optional[Any]:
        """Get min value of a column."""
        query = f"SELECT MIN({column}) as min_val FROM {table_name}"
        params = ()

        if where:
            conditions = " AND ".join([f"{k} = ?" for k in where.keys()])
            query += f" WHERE {conditions}"
            params = tuple(where.values())

        result = self.fetchone(query, params)
        return result["min_val"] if result else None

    def sum(
        self, table_name: str, column: str, where: Optional[Dict] = None
    ) -> Optional[float]:
        """Get sum of a column."""
        query = f"SELECT SUM({column}) as sum_val FROM {table_name}"
        params = ()

        if where:
            conditions = " AND ".join([f"{k} = ?" for k in where.keys()])
            query += f" WHERE {conditions}"
            params = tuple(where.values())

        result = self.fetchone(query, params)
        return result["sum_val"] if result else None

    def truncate(self, table_name: str) -> int:
        """Delete all rows from a table."""
        query = f"DELETE FROM {table_name}"
        cursor = self.execute(query)
        self.connection.commit()
        return cursor.rowcount

    def vacuum(self) -> bool:
        """Vacuum the database to reclaim space."""
        self.execute("VACUUM")
        self.connection.commit()
        return True

    def get_database_size(self) -> int:
        """Get database file size in bytes."""
        return self.db_path.stat().st_size if self.db_path.exists() else 0

    def backup(self, destination: Union[str, Path]) -> bool:
        """Backup database to another file."""
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        dest_conn = sqlite3.connect(str(dest_path))
        self.connection.backup(dest_conn)
        dest_conn.close()
        return True

    def restore(self, source: Union[str, Path]) -> bool:
        """Restore database from a backup file."""
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Backup file not found: {source}")

        self.close()

        import shutil

        shutil.copy2(source_path, self.db_path)

        self._connection = None
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def create_db(db_path: Union[str, Path]) -> SQLiteUtils:
    """Factory function to create a new SQLiteUtils instance."""
    return SQLiteUtils(db_path)


if __name__ == "__main__":
    import os
    import tempfile

    # Use temp directory for WSL compatibility
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "./demo_sqlite1.db")
    demo2_path = os.path.join(temp_dir, "./demo2_sqlite1.db")

    db = SQLiteUtils(db_path)

    print("=== SQLiteUtils Demo ===\n")

    db.create_table(
        "users",
        {"id": "INTEGER", "name": "TEXT", "email": "TEXT", "age": "INTEGER"},
        primary_key="id",
    )
    print("✓ Created 'users' table")

    db.insert("users", {"name": "Alice", "email": "alice@example.com", "age": 25})
    db.insert("users", {"name": "Bob", "email": "bob@example.com", "age": 30})
    print("✓ Inserted 2 users")

    users = db.select("users")
    print(f"\nAll users: {users}")

    user = db.select_one("users", where={"name": "Alice"})
    print(f"\nUser named Alice: {user}")

    db.update("users", {"age": 26}, where={"name": "Alice"})
    print("\n✓ Updated Alice's age to 26")

    db.delete("users", where={"name": "Bob"})
    print("✓ Deleted Bob")

    users = db.select("users")
    print(f"\nRemaining users: {users}")

    count = db.count("users")
    print(f"User count: {count}")

    print("\n=== Using Context Manager ===")
    with SQLiteUtils(demo2_path) as db2:
        db2.create_table("products", {"id": "INTEGER", "name": "TEXT", "price": "REAL"})
        db2.insert("products", {"name": "Widget", "price": 19.99})
        db2.insert("products", {"name": "Gadget", "price": 29.99})
        products = db2.select("products")
        print(f"Products: {products}")

    print("\n=== Demo Complete ===")
    db.close()

    # Cleanup temp files
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)
