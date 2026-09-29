"""API 查询公共辅助函数。"""

from __future__ import annotations

from typing import Any


def fetch_all(connection: Any, sql: str, params: tuple = ()) -> list[dict]:
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()


def fetch_one(connection: Any, sql: str, params: tuple = ()) -> dict | None:
    rows = fetch_all(connection, sql, params)
    return rows[0] if rows else None
