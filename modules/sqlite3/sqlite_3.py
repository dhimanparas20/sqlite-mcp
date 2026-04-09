from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


class SQLiteDB:
    """
    Production-oriented SQLite utility.

    Design goals:
    - dict/list-of-dict based CRUD
    - safe parameter binding for values
    - identifier validation for table/column names
    - transaction support
    - reusable across projects
    """

    _IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(
        self,
        db_path: str,
        *,
        timeout: float = 30.0,
        enable_wal: bool = True,
        foreign_keys: bool = True,
    ) -> None:
        self.db_path = db_path if db_path == ":memory:" else str(Path(db_path))
        self.conn = sqlite3.connect(
            self.db_path,
            timeout=timeout,
            check_same_thread=False,
            isolation_level=None,  # autocommit mode; explicit transaction() still works
        )
        self.conn.row_factory = sqlite3.Row
        self._tx_depth = 0

        if foreign_keys:
            self.conn.execute("PRAGMA foreign_keys = ON;")

        self.conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)};")

        if enable_wal and self.db_path != ":memory:":
            try:
                self.conn.execute("PRAGMA journal_mode = WAL;")
                self.conn.execute("PRAGMA synchronous = NORMAL;")
            except sqlite3.DatabaseError:
                # Some environments/filesystems may not support WAL
                pass

    # -------------------------------------------------------------------------
    # Context manager
    # -------------------------------------------------------------------------

    def __enter__(self) -> "SQLiteDB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc and self.conn.in_transaction:
                self.conn.rollback()
        finally:
            self.close()

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    # -------------------------------------------------------------------------
    # Transactions
    # -------------------------------------------------------------------------

    @contextmanager
    def transaction(self):
        """
        Supports nested transactions using SAVEPOINT.
        """
        if self._tx_depth == 0:
            self.conn.execute("BEGIN")
            self._tx_depth += 1
            try:
                yield self
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
            finally:
                self._tx_depth -= 1
        else:
            savepoint = f"sp_{self._tx_depth}"
            self.conn.execute(f"SAVEPOINT {savepoint}")
            self._tx_depth += 1
            try:
                yield self
                self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                self.conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            finally:
                self._tx_depth -= 1

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _quote_identifier(cls, name: str) -> str:
        if not isinstance(name, str) or not cls._IDENTIFIER_RE.fullmatch(name):
            raise ValueError(f"Invalid SQL identifier: {name!r}")
        return f'"{name}"'

    def _columns_sql(self, columns: str | Sequence[str]) -> str:
        if columns == "*":
            return "*"
        if isinstance(columns, str):
            return self._quote_identifier(columns)
        if not columns:
            return "*"
        return ", ".join(self._quote_identifier(col) for col in columns)

    def _order_by_sql(
        self,
        order_by: None | str | Sequence[str] | Sequence[tuple[str, str]],
    ) -> str:
        if not order_by:
            return ""

        if isinstance(order_by, str):
            return self._quote_identifier(order_by)

        parts = []
        for item in order_by:
            if isinstance(item, str):
                parts.append(self._quote_identifier(item))
            else:
                col, direction = item
                direction = direction.upper().strip()
                if direction not in {"ASC", "DESC"}:
                    raise ValueError("order_by direction must be 'ASC' or 'DESC'")
                parts.append(f"{self._quote_identifier(col)} {direction}")
        return ", ".join(parts)

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, Path):
            return str(value)
        return value

    def _deserialize_row(
        self,
        row: sqlite3.Row,
        json_columns: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        item = dict(row)
        if json_columns:
            for col in json_columns:
                if col in item and isinstance(item[col], str):
                    try:
                        item[col] = json.loads(item[col])
                    except json.JSONDecodeError:
                        pass
        return item

    def _compose_where(
        self,
        where: Mapping[str, Any] | None = None,
        where_sql: str | None = None,
        params: Sequence[Any] | None = None,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        all_params: list[Any] = []

        if where:
            for key, value in where.items():
                qkey = self._quote_identifier(key)

                if value is None:
                    clauses.append(f"{qkey} IS NULL")
                elif isinstance(value, (list, tuple, set)):
                    values = list(value)
                    if not values:
                        clauses.append("1 = 0")
                    else:
                        placeholders = ", ".join("?" for _ in values)
                        clauses.append(f"{qkey} IN ({placeholders})")
                        all_params.extend(self._serialize_value(v) for v in values)
                else:
                    clauses.append(f"{qkey} = ?")
                    all_params.append(self._serialize_value(value))

        if where_sql:
            clauses.append(f"({where_sql})")
            if params:
                all_params.extend(self._serialize_value(v) for v in params)

        if not clauses:
            return "", all_params

        return " WHERE " + " AND ".join(clauses), all_params

    def _map_rows(
        self,
        rows: list[sqlite3.Row],
        *,
        json_columns: Sequence[str] | None = None,
        mapper: Callable[[dict[str, Any]], Any] | None = None,
    ) -> list[Any]:
        items = [self._deserialize_row(row, json_columns=json_columns) for row in rows]
        if mapper:
            return [mapper(item) for item in items]
        return items

    # -------------------------------------------------------------------------
    # Low-level execution
    # -------------------------------------------------------------------------

    def execute(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
    ) -> sqlite3.Cursor:
        cur = self.conn.cursor()
        cur.execute(sql, params or [])
        return cur

    def executemany(
        self,
        sql: str,
        seq_of_params: Iterable[Sequence[Any]],
    ) -> sqlite3.Cursor:
        cur = self.conn.cursor()
        cur.executemany(sql, seq_of_params)
        return cur

    def query(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        *,
        json_columns: Sequence[str] | None = None,
        mapper: Callable[[dict[str, Any]], Any] | None = None,
    ) -> list[Any]:
        cur = self.execute(sql, params)
        rows = cur.fetchall()
        return self._map_rows(rows, json_columns=json_columns, mapper=mapper)

    def query_one(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        *,
        json_columns: Sequence[str] | None = None,
        mapper: Callable[[dict[str, Any]], Any] | None = None,
    ) -> Any | None:
        cur = self.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        item = self._deserialize_row(row, json_columns=json_columns)
        return mapper(item) if mapper else item

    # -------------------------------------------------------------------------
    # Schema / table utilities
    # -------------------------------------------------------------------------

    def list_tables(self) -> list[str]:
        rows = self.query("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        return [row["name"] for row in rows]

    def table_exists(self, table: str) -> bool:
        row = self.query_one(
            """
            SELECT 1 AS found
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            [table],
        )
        return row is not None

    def table_info(self, table: str) -> list[dict[str, Any]]:
        return self.query(f"PRAGMA table_info({self._quote_identifier(table)})")

    def create_table(
        self,
        table: str,
        columns: Mapping[str, str],
        *,
        table_constraints: Sequence[str] | None = None,
        if_not_exists: bool = True,
        strict: bool = False,
    ) -> None:
        if not columns:
            raise ValueError("columns cannot be empty")

        parts = [
            f"{self._quote_identifier(name)} {definition}"
            for name, definition in columns.items()
        ]
        if table_constraints:
            parts.extend(table_constraints)

        sql = f"CREATE TABLE {'IF NOT EXISTS ' if if_not_exists else ''}{self._quote_identifier(table)} ({', '.join(parts)})"
        if strict:
            sql += " STRICT"

        self.execute(sql)

    def drop_table(self, table: str, *, if_exists: bool = True) -> None:
        sql = f"DROP TABLE {'IF EXISTS ' if if_exists else ''}{self._quote_identifier(table)}"
        self.execute(sql)

    def rename_table(self, old_name: str, new_name: str) -> None:
        sql = f"ALTER TABLE {self._quote_identifier(old_name)} RENAME TO {self._quote_identifier(new_name)}"
        self.execute(sql)

    def add_column(self, table: str, column_name: str, definition: str) -> None:
        sql = f"ALTER TABLE {self._quote_identifier(table)} ADD COLUMN {self._quote_identifier(column_name)} {definition}"
        self.execute(sql)

    def create_index(
        self,
        table: str,
        columns: Sequence[str],
        *,
        name: str | None = None,
        unique: bool = False,
        if_not_exists: bool = True,
    ) -> None:
        if not columns:
            raise ValueError("columns cannot be empty")

        idx_name = name or f"idx_{table}_{'_'.join(columns)}"
        cols_sql = ", ".join(self._quote_identifier(c) for c in columns)

        sql = (
            f"CREATE {'UNIQUE ' if unique else ''}INDEX "
            f"{'IF NOT EXISTS ' if if_not_exists else ''}"
            f"{self._quote_identifier(idx_name)} "
            f"ON {self._quote_identifier(table)} ({cols_sql})"
        )
        self.execute(sql)

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def insert(
        self,
        table: str,
        data: Mapping[str, Any],
        *,
        return_row: bool = False,
        json_columns: Sequence[str] | None = None,
        mapper: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any] | Any | None:
        if not data:
            raise ValueError("data cannot be empty")

        columns = list(data.keys())
        values = [self._serialize_value(data[col]) for col in columns]

        sql = (
            f"INSERT INTO {self._quote_identifier(table)} "
            f"({', '.join(self._quote_identifier(c) for c in columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})"
        )
        cur = self.execute(sql, values)

        if return_row:
            if "id" in data:
                return self.select_one(
                    table,
                    where={"id": data["id"]},
                    json_columns=json_columns,
                    mapper=mapper,
                )
            if cur.lastrowid:
                return self.query_one(
                    f"SELECT * FROM {self._quote_identifier(table)} WHERE rowid = ?",
                    [cur.lastrowid],
                    json_columns=json_columns,
                    mapper=mapper,
                )
            return None

        return {"lastrowid": cur.lastrowid, "rowcount": cur.rowcount}

    def insert_many(
        self,
        table: str,
        rows: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        rows = list(rows)
        if not rows:
            return {"rowcount": 0}

        columns = list(rows[0].keys())
        col_set = set(columns)

        for row in rows:
            if set(row.keys()) != col_set:
                raise ValueError("All rows in insert_many must have the same keys")

        values = [[self._serialize_value(row[col]) for col in columns] for row in rows]

        sql = (
            f"INSERT INTO {self._quote_identifier(table)} "
            f"({', '.join(self._quote_identifier(c) for c in columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})"
        )

        cur = self.executemany(sql, values)
        return {"rowcount": cur.rowcount}

    def select(
        self,
        table: str,
        *,
        columns: str | Sequence[str] = "*",
        where: Mapping[str, Any] | None = None,
        where_sql: str | None = None,
        params: Sequence[Any] | None = None,
        order_by: None | str | Sequence[str] | Sequence[tuple[str, str]] = None,
        limit: int | None = None,
        offset: int | None = None,
        json_columns: Sequence[str] | None = None,
        mapper: Callable[[dict[str, Any]], Any] | None = None,
    ) -> list[Any]:
        sql = (
            f"SELECT {self._columns_sql(columns)} FROM {self._quote_identifier(table)}"
        )

        where_clause, all_params = self._compose_where(where, where_sql, params)
        sql += where_clause

        order_sql = self._order_by_sql(order_by)
        if order_sql:
            sql += f" ORDER BY {order_sql}"

        if limit is not None:
            sql += " LIMIT ?"
            all_params.append(int(limit))

            if offset is not None:
                sql += " OFFSET ?"
                all_params.append(int(offset))
        elif offset is not None:
            sql += " LIMIT -1 OFFSET ?"
            all_params.append(int(offset))

        return self.query(sql, all_params, json_columns=json_columns, mapper=mapper)

    def select_one(
        self,
        table: str,
        *,
        columns: str | Sequence[str] = "*",
        where: Mapping[str, Any] | None = None,
        where_sql: str | None = None,
        params: Sequence[Any] | None = None,
        order_by: None | str | Sequence[str] | Sequence[tuple[str, str]] = None,
        json_columns: Sequence[str] | None = None,
        mapper: Callable[[dict[str, Any]], Any] | None = None,
    ) -> Any | None:
        rows = self.select(
            table,
            columns=columns,
            where=where,
            where_sql=where_sql,
            params=params,
            order_by=order_by,
            limit=1,
            json_columns=json_columns,
            mapper=mapper,
        )
        return rows[0] if rows else None

    def update(
        self,
        table: str,
        data: Mapping[str, Any],
        *,
        where: Mapping[str, Any] | None = None,
        where_sql: str | None = None,
        params: Sequence[Any] | None = None,
        allow_all: bool = False,
    ) -> dict[str, Any]:
        if not data:
            raise ValueError("data cannot be empty")

        where_clause, where_params = self._compose_where(where, where_sql, params)
        if not where_clause and not allow_all:
            raise ValueError("Refusing to UPDATE all rows without allow_all=True")

        set_clause = ", ".join(
            f"{self._quote_identifier(col)} = ?" for col in data.keys()
        )
        set_params = [self._serialize_value(v) for v in data.values()]

        sql = f"UPDATE {self._quote_identifier(table)} SET {set_clause}{where_clause}"
        cur = self.execute(sql, set_params + where_params)
        return {"rowcount": cur.rowcount}

    def delete(
        self,
        table: str,
        *,
        where: Mapping[str, Any] | None = None,
        where_sql: str | None = None,
        params: Sequence[Any] | None = None,
        allow_all: bool = False,
    ) -> dict[str, Any]:
        where_clause, where_params = self._compose_where(where, where_sql, params)
        if not where_clause and not allow_all:
            raise ValueError("Refusing to DELETE all rows without allow_all=True")

        sql = f"DELETE FROM {self._quote_identifier(table)}{where_clause}"
        cur = self.execute(sql, where_params)
        return {"rowcount": cur.rowcount}

    def upsert(
        self,
        table: str,
        data: Mapping[str, Any],
        conflict_columns: str | Sequence[str],
        *,
        update_columns: Sequence[str] | None = None,
        do_nothing: bool = False,
        return_row: bool = False,
        json_columns: Sequence[str] | None = None,
        mapper: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any] | Any | None:
        if not data:
            raise ValueError("data cannot be empty")

        if isinstance(conflict_columns, str):
            conflict_columns = [conflict_columns]
        conflict_columns = list(conflict_columns)

        columns = list(data.keys())
        values = [self._serialize_value(data[col]) for col in columns]

        insert_sql = (
            f"INSERT INTO {self._quote_identifier(table)} "
            f"({', '.join(self._quote_identifier(c) for c in columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})"
        )

        conflict_sql = ", ".join(self._quote_identifier(c) for c in conflict_columns)

        if do_nothing:
            sql = f"{insert_sql} ON CONFLICT ({conflict_sql}) DO NOTHING"
        else:
            update_columns = (
                list(update_columns)
                if update_columns is not None
                else [c for c in columns if c not in conflict_columns]
            )

            if not update_columns:
                sql = f"{insert_sql} ON CONFLICT ({conflict_sql}) DO NOTHING"
            else:
                set_clause = ", ".join(
                    f"{self._quote_identifier(c)} = excluded.{self._quote_identifier(c)}"
                    for c in update_columns
                )
                sql = f"{insert_sql} ON CONFLICT ({conflict_sql}) DO UPDATE SET {set_clause}"

        cur = self.execute(sql, values)

        if return_row:
            if all(c in data for c in conflict_columns):
                where = {c: data[c] for c in conflict_columns}
                return self.select_one(
                    table,
                    where=where,
                    json_columns=json_columns,
                    mapper=mapper,
                )
            if cur.lastrowid:
                return self.query_one(
                    f"SELECT * FROM {self._quote_identifier(table)} WHERE rowid = ?",
                    [cur.lastrowid],
                    json_columns=json_columns,
                    mapper=mapper,
                )
            return None

        return {"lastrowid": cur.lastrowid, "rowcount": cur.rowcount}

    def count(
        self,
        table: str,
        *,
        where: Mapping[str, Any] | None = None,
        where_sql: str | None = None,
        params: Sequence[Any] | None = None,
    ) -> int:
        where_clause, where_params = self._compose_where(where, where_sql, params)
        row = self.query_one(
            f"SELECT COUNT(*) AS count FROM {self._quote_identifier(table)}{where_clause}",
            where_params,
        )
        return int(row["count"]) if row else 0

    def exists(
        self,
        table: str,
        *,
        where: Mapping[str, Any] | None = None,
        where_sql: str | None = None,
        params: Sequence[Any] | None = None,
    ) -> bool:
        where_clause, where_params = self._compose_where(where, where_sql, params)
        row = self.query_one(
            f"SELECT 1 AS found FROM {self._quote_identifier(table)}{where_clause} LIMIT 1",
            where_params,
        )
        return row is not None

    # -------------------------------------------------------------------------
    # Maintenance
    # -------------------------------------------------------------------------

    def vacuum(self) -> None:
        self.execute("VACUUM")

    def backup_to(self, target_path: str) -> None:
        with sqlite3.connect(target_path) as target:
            self.conn.backup(target)


if __name__ == "__main__":
    import os
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "./demo_sqlite3.db")
    demo3_path = os.path.join(temp_dir, "./demo2_sqlite1.db")

    print("=== SQLiteDB Demo ===\n")

    db = SQLiteDB(db_path)

    db.create_table(
        "inventory",
        {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "name": "TEXT NOT NULL UNIQUE",
            "quantity": "INTEGER DEFAULT 0",
            "price": "REAL",
        },
    )
    print("✓ Created 'inventory' table")

    db.insert("inventory", {"name": "Apple", "quantity": 100, "price": 0.50})
    db.insert("inventory", {"name": "Banana", "quantity": 50, "price": 0.30})
    db.insert("inventory", {"name": "Orange", "quantity": 75, "price": 0.75})
    print("✓ Inserted 3 items")

    items = db.select("inventory")
    print(f"\nAll items: {items}")

    item = db.select_one("inventory", where={"name": "Apple"})
    print(f"\nApple: {item}")

    db.update("inventory", {"quantity": 90}, where={"name": "Apple"})
    print("\n✓ Updated Apple quantity")

    db.delete("inventory", where={"name": "Banana"})
    print("✓ Deleted Banana")

    items = db.select("inventory")
    print(f"\nRemaining items: {items}")

    count = db.count("inventory")
    print(f"Item count: {count}")

    print("\n=== Upsert Demo ===")
    db.upsert(
        "inventory",
        {"name": "Apple", "quantity": 80, "price": 0.60},
        conflict_columns=["name"],
    )
    item = db.select_one("inventory", where={"name": "Apple"})
    print(f"After upsert: {item}")

    print("\n=== Insert Many Demo ===")
    db.insert_many(
        "inventory",
        [
            {"name": f"Item{i}", "quantity": i * 10, "price": i * 1.5}
            for i in range(1, 6)
        ],
    )
    items = db.select("inventory")
    print(f"All items after bulk insert: {items}")

    print("\n=== Using Context Manager ===")
    with SQLiteDB(demo3_path) as db2:
        db2.create_table(
            "orders", {"id": "INTEGER PRIMARY KEY", "item": "TEXT", "qty": "INTEGER"}
        )
        db2.insert("orders", {"item": "Laptop", "qty": 1})
        orders = db2.select("orders")
        print(f"Orders: {orders}")

    print("\n=== Transaction Demo ===")
    with db.transaction():
        db.insert("inventory", {"name": "Mango", "quantity": 25, "price": 1.00})
        db.insert("inventory", {"name": "Grape", "quantity": 40, "price": 2.00})
    print("✓ Transaction committed")

    items = db.select("inventory")
    print(f"Total items after transaction: {len(items)}")

    print("\n=== Demo Complete ===")
    db.close()

    shutil.rmtree(temp_dir, ignore_errors=True)
