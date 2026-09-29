from fastapi import APIRouter, HTTPException, Query

from backend.agent.tools.clip_tool import ClipTool
from backend.api.helpers import fetch_all, fetch_one
from backend.database.connection import database

router = APIRouter(prefix="/api", tags=["clips"])


@router.get("/videos/{video_id}/clips")
def clips(
    video_id: int,
    person_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    event: str | None = Query(default=None),
    start_time: float | None = Query(default=None, ge=0),
    end_time: float | None = Query(default=None, ge=0),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
) -> list[dict]:
    if start_time is not None and end_time is not None and end_time < start_time:
        raise HTTPException(status_code=422, detail="结束时间不能早于开始时间")
    try:
        connection = database.get()
        video = fetch_one(connection, "SELECT duration FROM dbo.videos WHERE video_id=?", (video_id,))
        if video is None:
            raise HTTPException(status_code=404, detail="视频不存在")
        rows = []
        if action:
            sql = """SELECT p.person_id,b.action,b.start_time,b.end_time,b.confidence
                FROM dbo.behaviors b JOIN dbo.persons p ON p.id=b.person_id WHERE p.video_id=?"""
            params = [video_id]
            if person_id is not None:
                sql += " AND p.person_id=?"; params.append(person_id)
            sql += " AND b.action=?"; params.append(action)
            rows = fetch_all(connection, sql + " ORDER BY b.start_time", tuple(params))
        elif event:
            sql = """SELECT p.person_id,a.event,a.start_time,a.end_time,a.confidence,a.severity
                FROM dbo.anomalies a JOIN dbo.persons p ON p.id=a.person_id WHERE p.video_id=?"""
            params = [video_id]
            if person_id is not None:
                sql += " AND p.person_id=?"; params.append(person_id)
            sql += " AND a.event=?"; params.append(event)
            rows = fetch_all(connection, sql + " ORDER BY a.start_time", tuple(params))
        else:
            raise HTTPException(status_code=422, detail="action 和 event 至少提供一个")
        if start_time is not None:
            rows = [row for row in rows if float(row["end_time"]) >= start_time]
        if end_time is not None:
            rows = [row for row in rows if float(row["start_time"]) <= end_time]
        return ClipTool().build(video_id, rows, action or event, video.get("duration"), min_confidence)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"片段查询失败：{exc}") from exc
