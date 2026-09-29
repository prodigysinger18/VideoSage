"""复用项目 SQL Server 配置的长连接管理器。"""

from __future__ import annotations

from threading import Lock, local
from typing import Any, Optional

from core.config_loader import get_section, load_config
from database.sqlserver_manager import SQLServerManager


class DatabaseConnection:
    """按工作线程复用独立连接，避免 pyodbc 同连接并发执行命令。"""

    def __init__(self, config_path: Optional[str] = None) -> None:
        config = load_config(config_path)
        self._config = get_section(config, "database")
        self._local = local()
        self._lock = Lock()
        self._managers = set()

    def get(self) -> Any:
        manager = getattr(self._local, "manager", None)
        with self._lock:
            if manager is None or manager.connection is None:
                manager = SQLServerManager(self._config)
                manager.connect()
                self._local.manager = manager
                self._managers.add(manager)
            return manager.connection

    def close_current(self) -> None:
        manager = getattr(self._local, "manager", None)
        if manager is None:
            return
        with self._lock:
            manager.close()
            self._managers.discard(manager)
            self._local.manager = None

    def close(self) -> None:
        with self._lock:
            for manager in tuple(self._managers):
                manager.close()
            self._managers.clear()
            self._local.manager = None


database = DatabaseConnection()
