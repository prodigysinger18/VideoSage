"""VideoSage FastAPI 服务。"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent.video_agent import VideoAgent


class ChatRequest(BaseModel):
    video_id: int = Field(gt=0)
    question: str = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str
    intent: str
    data: object


app = FastAPI(title="VideoSage API", version="1.0.0")


@lru_cache(maxsize=1)
def get_agent() -> VideoAgent:
    return VideoAgent()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    try:
        return get_agent().chat(request.question, request.video_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"查询服务暂时不可用：{exc}") from exc


@app.on_event("shutdown")
def shutdown() -> None:
    if get_agent.cache_info().currsize:
        get_agent().close()
        get_agent.cache_clear()
