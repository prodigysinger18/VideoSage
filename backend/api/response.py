"""统一 HTTP 响应格式。"""

from __future__ import annotations

from typing import Any


def success_response(data: Any, request_id: str, message: str = "") -> dict:
    return {
        "success": True,
        "data": data,
        "message": message,
        "request_id": request_id,
    }


def error_response(code: str, message: str, request_id: str) -> dict:
    return {
        "success": False,
        "data": None,
        "error_code": code,
        "message": message,
        "request_id": request_id,
    }
