"""可选的本机 API Key 防护。"""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse

from core.config_loader import get_value, load_config


def configured_api_key() -> str:
    return os.getenv("VIDEOSAGE_API_KEY", "") or str(
        get_value(load_config(), "security.api_key", "") or ""
    )


def check_api_key(request: Request) -> JSONResponse | None:
    expected = configured_api_key()
    if not expected or request.url.path.startswith(("/health", "/docs", "/redoc", "/openapi.json")):
        return None
    supplied = request.headers.get("X-API-Key", "")
    if not supplied:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
    if supplied != expected:
        return JSONResponse(status_code=401, content={"detail": "API Key 无效或缺失"})
    return None
