"""查询层数据库连接封装。"""

from __future__ import annotations

from typing import Any, Optional

from core.config_loader import load_config, get_section
from database.sqlserver_manager import SQLServerManager


class QueryDatabase:
    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config = load_config(config_path)
        self.manager = SQLServerManager(get_section(self.config, "database"))

    def get_connection(self) -> Any:
        return self.manager.connect().connection

    def close_connection(self) -> None:
        self.manager.close()

    def __enter__(self) -> "QueryDatabase":
        self.get_connection()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close_connection()
