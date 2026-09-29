from fastapi import APIRouter, HTTPException

from backend.database.connection import database
from backend.api.helpers import fetch_all, fetch_one

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard() -> dict:
    try:
        row = fetch_one(
            database.get(),
            """SELECT
                (SELECT COUNT(*) FROM dbo.videos) AS video_count,
                (SELECT COUNT(*) FROM dbo.persons) AS person_count,
                (SELECT COUNT(*) FROM dbo.behaviors) AS behavior_count,
                (SELECT COUNT(*) FROM dbo.anomalies) AS anomaly_count""",
        ) or {}
        result = {key: int(row.get(key) or 0) for key in (
            "video_count", "person_count", "behavior_count", "anomaly_count"
        )}
        behavior_rows = fetch_all(database.get(), "SELECT action, COUNT(*) AS count FROM dbo.behaviors GROUP BY action")
        anomaly_rows = fetch_all(database.get(), "SELECT event, COUNT(*) AS count FROM dbo.anomalies GROUP BY event")
        result["behavior_distribution"] = {item["action"]: int(item["count"]) for item in behavior_rows}
        result["anomaly_distribution"] = {item["event"]: int(item["count"]) for item in anomaly_rows}
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库查询失败：{exc}") from exc
