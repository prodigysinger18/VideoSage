from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agent.agent import VideoQuestionAgent

router = APIRouter(prefix="/api", tags=["agent"])
agent = VideoQuestionAgent()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    video_id: int | None = Field(default=None, gt=0)
    conversation_id: str | None = Field(default=None, max_length=128)


@router.post("/chat")
def chat(request: ChatRequest) -> dict:
    if request.video_id is None:
        raise HTTPException(status_code=422, detail="请选择视频")
    try:
        return agent.chat(request.question, request.video_id, request.conversation_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库查询失败：{exc}") from exc
