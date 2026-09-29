"""FastAPI 错误响应处理。"""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.response import error_response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "HTTP_ERROR"
    if exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 422:
        code = "VALIDATION_ERROR"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code, str(exc.detail), _request_id(request)),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_response("VALIDATION_ERROR", "请求参数格式错误", _request_id(request)),
    )
