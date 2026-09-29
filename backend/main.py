"""VideoSage Stage 8 FastAPI 后端入口。"""

from contextlib import asynccontextmanager
import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.agent_api import router as agent_router
from backend.api.anomaly_api import router as anomaly_router
from backend.api.behavior_api import router as behavior_router
from backend.api.dashboard_api import router as dashboard_router
from backend.api.clip_api import router as clip_router
from backend.api.person_api import router as person_router
from backend.api.video_api import router as video_router
from backend.api.health_api import router as health_router
from backend.database.connection import database
from backend.api.errors import http_exception_handler, validation_exception_handler
from backend.api.response import success_response
from backend.api.security import check_api_key
from utils.logging_config import configure_logging, environment_log_level


configure_logging(environment_log_level())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    database.close()


app = FastAPI(title="VideoSage Backend", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def unified_response(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    denied = check_api_key(request)
    if denied is not None:
        denied.headers["X-Request-ID"] = request_id
        return denied
    response = await call_next(request)
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    response.headers["X-Request-ID"] = request_id
    if response.headers.get("content-type", "").startswith("application/json"):
        body = getattr(response, "body", None)
        if body is None and hasattr(response, "body_iterator"):
            chunks = [chunk async for chunk in response.body_iterator]
            body = b"".join(chunks)
        if body:
            try:
                payload = json.loads(body)
                if not isinstance(payload, dict) or "success" not in payload:
                    payload = success_response(payload, request_id)
                response = JSONResponse(
                    status_code=response.status_code,
                    content=payload,
                    headers={"X-Request-ID": request_id},
                )
            except (TypeError, ValueError):
                pass
    return response


app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in (dashboard_router, video_router, person_router, behavior_router, anomaly_router, clip_router, agent_router, health_router):
    app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
