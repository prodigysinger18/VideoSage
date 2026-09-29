"""基于结构化分析结果生成视频级摘要。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.api.helpers import fetch_all, fetch_one


class SummaryTool:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def query(self, video_id: int, requested_person_id: int | None = None) -> dict:
        video = fetch_one(self.connection, """SELECT video_id,video_name,duration,fps,width,height
            FROM dbo.videos WHERE video_id=?""", (video_id,)) or {}
        if not video:
            return {}
        persons = fetch_all(self.connection, """SELECT person_id,first_seen,last_seen,appearance_json
            FROM dbo.persons WHERE video_id=? ORDER BY person_id""", (video_id,))
        behaviors = fetch_all(self.connection, """SELECT p.person_id,b.action,b.start_time,b.end_time,b.confidence
            FROM dbo.behaviors b JOIN dbo.persons p ON p.id=b.person_id
            WHERE p.video_id=? ORDER BY b.start_time,p.person_id""", (video_id,))
        anomalies = fetch_all(self.connection, """SELECT p.person_id,a.event,a.severity,a.start_time,a.end_time,a.confidence
            FROM dbo.anomalies a JOIN dbo.persons p ON p.id=a.person_id
            WHERE p.video_id=? ORDER BY a.start_time,p.person_id""", (video_id,))
        actions_by_person = defaultdict(list)
        anomalies_by_person = defaultdict(list)
        for item in behaviors:
            actions_by_person[int(item["person_id"])].append({
                "action": item["action"], "start_time": item["start_time"],
                "end_time": item["end_time"], "confidence": item["confidence"],
            })
        for item in anomalies:
            anomalies_by_person[int(item["person_id"])].append({
                "person_id": int(item["person_id"]),
                "event": item["event"], "severity": item["severity"],
                "start_time": item["start_time"], "end_time": item["end_time"],
                "confidence": item["confidence"],
            })
        person_summaries = []
        for person in persons:
            person_id = int(person["person_id"])
            person_summaries.append({
                "person_id": person_id,
                "first_seen": person["first_seen"],
                "last_seen": person["last_seen"],
                "appearance": _safe_json(person.get("appearance_json")),
                "actions": actions_by_person[person_id][:30],
                "anomalies": anomalies_by_person[person_id][:30],
            })
        if requested_person_id is not None:
            person_summaries = [item for item in person_summaries if item["person_id"] == requested_person_id]
        key_events = sorted(
            [event for events in anomalies_by_person.values() for event in events],
            key=lambda item: float(item.get("start_time") or 0),
        )[:50]
        return {
            "video": video,
            "person_count": len(person_summaries),
            "behavior_count": len(behaviors),
            "anomaly_count": len(anomalies),
            "persons": person_summaries,
            "key_events": [
                item for item in key_events
                if requested_person_id is None or item.get("person_id") == requested_person_id
            ],
        }


def _safe_json(value: Any) -> dict:
    if not value:
        return {}
    import json
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}
