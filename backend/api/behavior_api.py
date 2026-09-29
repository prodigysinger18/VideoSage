from fastapi import APIRouter, HTTPException

from backend.database.connection import database
from backend.api.helpers import fetch_all

router = APIRouter(prefix="/api", tags=["behaviors"])


@router.get("/behaviors/{video_id}")
def behaviors(video_id: int) -> list[dict]:
    try:
        return fetch_all(database.get(), """SELECT p.person_id,b.action,b.start_time,b.end_time,b.confidence
            FROM dbo.behaviors b JOIN dbo.persons p ON p.id=b.person_id
            WHERE p.video_id=? ORDER BY b.start_time,p.person_id""", (video_id,))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库查询失败：{exc}") from exc
