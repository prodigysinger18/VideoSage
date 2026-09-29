"""项目统一日志配置。"""

from __future__ import annotations

import logging
import os


def configure_logging(level: str = "INFO") -> None:
    """配置一次进程级日志，避免业务模块重复添加 handler。"""
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
        return
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def environment_log_level(default: str = "INFO") -> str:
    return os.getenv("VIDEOSAGE_LOG_LEVEL", default)
