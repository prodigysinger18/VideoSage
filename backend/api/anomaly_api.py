import json

from fastapi import APIRouter, HTTPException

from backend.database.connection import database
from backend.api.helpers import fetch_all

router = APIRouter(prefix="/api", tags=["anomalies"])


@router.get("/anomalies/{video_id}")
def anomalies(video_id: int) -> list[dict]:
    try:
        rows = fetch_all(database.get(), """SELECT p.person_id,a.event,a.start_time,a.end_time,a.confidence,a.severity,p.appearance_json
            FROM dbo.anomalies a JOIN dbo.persons p ON p.id=a.person_id
            WHERE p.video_id=? ORDER BY a.start_time,p.person_id""", (video_id,))
        for row in rows:
            try:
                appearance = json.loads(row.pop("appearance_json") or "{}")
            except (TypeError, ValueError):
                appearance = {}
            upper, lower = appearance.get("upper") or {}, appearance.get("lower") or {}
            row["outfit"] = {"upper_color": upper.get("color"), "upper_type": upper.get("type"), "lower_color": lower.get("color"), "lower_type": lower.get("type")}
        return rows
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库查询失败：{exc}") from exc
