"""服务存活和依赖就绪检查。"""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database.connection import database
from core.config_loader import get_section, get_value, load_config, resolve_path


router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict:
    """只检查 FastAPI 进程是否可以响应请求。"""
    return {"status": "ok", "service": "videosage-backend"}


@router.get("/health/ready")
def readiness() -> JSONResponse:
    """检查配置、结果目录和 SQL Server 是否可用。"""
    checks: dict[str, dict[str, object]] = {}
    config = load_config()

    results_root = resolve_path(
        config,
        get_value(config, "paths.results_dir", "data/results"),
    )
    checks["config"] = {"ok": True, "path": config.get("_config_path")}
    checks["results_directory"] = {
        "ok": bool(results_root and os.path.isdir(results_root)),
        "path": results_root,
    }

    database_config = get_section(config, "database")
    if not bool(database_config.get("enabled", True)):
        checks["database"] = {"ok": True, "enabled": False}
    else:
        try:
            connection = database.get()
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                cursor.close()
            checks["database"] = {"ok": True, "enabled": True}
        except Exception as exc:
            database.close_current()
            checks["database"] = {
                "ok": False,
                "enabled": True,
                "error": str(exc),
            }

    ready = all(bool(item.get("ok")) for item in checks.values())
    payload = {
        "status": "ok" if ready else "not_ready",
        "checks": checks,
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)
