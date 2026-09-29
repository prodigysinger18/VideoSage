"""SQL Server 连接和基础执行封装。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from database.database_schema import CREATE_TABLE_STATEMENTS


class SQLServerManager:
    """管理 pyodbc 连接、建表和参数化 SQL 执行。"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = dict(config or {})
        self.connection: Any = None

    def connect(self) -> "SQLServerManager":
        if self.connection is not None:
            return self
        if not bool(self.config.get("enabled", True)):
            raise RuntimeError("数据库功能已在配置中禁用")

        try:
            import pyodbc
        except ImportError as exc:
            raise RuntimeError("缺少 pyodbc，请在当前项目环境中安装 pyodbc") from exc

        driver = self.config.get("driver", "ODBC Driver 17 for SQL Server")
        server = self.config.get("server", "localhost")
        database = self.config.get("database", "VideoSageDB")
        username = str(self.config.get("username", "") or "")
        password = str(self.config.get("password", "") or "")

        parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={server}",
            f"DATABASE={database}",
        ]
        if username:
            parts.extend((f"UID={username}", f"PWD={password}"))
        else:
            parts.append("Trusted_Connection=yes")

        self.connection = pyodbc.connect(";".join(parts), autocommit=False)
        return self

    def create_tables(self) -> None:
        self._require_connection()
        cursor = self.connection.cursor()
        try:
            for statement in CREATE_TABLE_STATEMENTS:
                cursor.execute(statement)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def execute(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
        commit: bool = False,
    ) -> Any:
        self._require_connection()
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(params or ()))
            if commit:
                self.connection.commit()
            return cursor
        except Exception:
            cursor.close()
            if commit:
                self.connection.rollback()
            raise

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _require_connection(self) -> None:
        if self.connection is None:
            raise RuntimeError("SQL Server 尚未连接，请先调用 connect()")

    def __enter__(self) -> "SQLServerManager":
        return self.connect()

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()
