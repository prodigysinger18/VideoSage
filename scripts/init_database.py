"""初始化 VideoSage SQL Server 表结构。"""

from __future__ import annotations

import argparse

from core.config_loader import get_section, load_config
from database.sqlserver_manager import SQLServerManager


def main() -> int:
    parser = argparse.ArgumentParser(description="创建或校验 VideoSage SQL Server 表")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    with SQLServerManager(get_section(config, "database")) as manager:
        manager.create_tables()
    print("database_schema=ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
