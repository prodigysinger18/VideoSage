import json

from fastapi import APIRouter, HTTPException

from backend.database.connection import database
from backend.api.helpers import fetch_all

router = APIRouter(prefix="/api", tags=["persons"])


@router.get("/outfits/{video_id}")
def outfits(video_id: int) -> list[dict]:
    try:
        rows = fetch_all(database.get(), """SELECT person_id, appearance_json AS outfit
            FROM dbo.persons WHERE video_id=? ORDER BY person_id""", (video_id,))
        for row in rows:
            try:
                row["outfit"] = json.loads(row["outfit"] or "{}")
            except (TypeError, ValueError):
                row["outfit"] = {}
        return rows
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库查询失败：{exc}") from exc


@router.get("/persons/{video_id}")
def persons(video_id: int) -> list[dict]:
    try:
        rows = fetch_all(database.get(), """SELECT person_id,
            first_seen, last_seen, appearance_json AS outfit
            FROM dbo.persons WHERE video_id = ? ORDER BY person_id""", (video_id,))
        for row in rows:
            row["track_id"] = None
            row["actions"] = fetch_all(database.get(), """SELECT b.action,b.start_time,b.end_time,b.confidence
                FROM dbo.behaviors b JOIN dbo.persons p ON p.id=b.person_id
                WHERE p.video_id=? AND p.person_id=? ORDER BY b.start_time""", (video_id, row["person_id"]))
            durations = {}
            for action in row["actions"]:
                duration = float(action["end_time"] or 0) - float(action["start_time"] or 0)
                durations[action["action"]] = durations.get(action["action"], 0.0) + max(0.0, duration)
            row["primary_action"] = max(durations, key=durations.get) if durations else "unknown"
            row["trajectory"] = []
            try:
                row["outfit"] = json.loads(row["outfit"] or "{}")
            except (TypeError, ValueError):
                row["outfit"] = {}
        return rows
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库查询失败：{exc}") from exc


@router.get("/videos/{video_id}/persons/{person_id}")
def person_detail(video_id: int, person_id: int) -> dict:
    try:
        person = fetch_all(database.get(), """SELECT person_id, first_seen, last_seen,
            appearance_json AS outfit FROM dbo.persons
            WHERE video_id = ? AND person_id = ?""", (video_id, person_id))
        if not person:
            raise HTTPException(status_code=404, detail="人物不存在")
        row = person[0]
        row["track_id"] = None
        row["trajectory"] = []
        try:
            row["outfit"] = json.loads(row["outfit"] or "{}")
        except (TypeError, ValueError):
            row["outfit"] = {}
        row["behaviors"] = fetch_all(database.get(), """SELECT action,start_time,end_time,confidence
            FROM dbo.behaviors b JOIN dbo.persons p ON p.id=b.person_id
            WHERE p.video_id=? AND p.person_id=? ORDER BY start_time""", (video_id, person_id))
        row["anomalies"] = fetch_all(database.get(), """SELECT event,severity,start_time,end_time,confidence
            FROM dbo.anomalies a JOIN dbo.persons p ON p.id=a.person_id
            WHERE p.video_id=? AND p.person_id=? ORDER BY start_time""", (video_id, person_id))
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库查询失败：{exc}") from exc
