import json

from backend.api.helpers import fetch_all


class AnomalyTool:
    def __init__(self, connection): self.connection = connection

    def query(self, video_id: int, person_id: int | None = None, event: str | None = None) -> list[dict]:
        sql = """SELECT p.person_id,a.event,a.severity,a.start_time,a.end_time,a.confidence,
            p.appearance_json
            FROM dbo.anomalies a JOIN dbo.persons p ON p.id=a.person_id WHERE p.video_id=?"""
        params = [video_id]
        if person_id is not None:
            sql += " AND p.person_id=?"; params.append(person_id)
        if event:
            sql += " AND a.event=?"; params.append(event)
        rows = fetch_all(self.connection, sql + " ORDER BY a.start_time", tuple(params))
        for row in rows:
            try:
                appearance = json.loads(row.pop("appearance_json") or "{}")
            except (TypeError, ValueError):
                appearance = {}
            upper = appearance.get("upper") or {}
            lower = appearance.get("lower") or {}
            row["outfit"] = {
                "upper_color": upper.get("color"),
                "upper_type": upper.get("type"),
                "upper_sleeve": upper.get("sleeve"),
                "lower_color": lower.get("color"),
                "lower_type": lower.get("type"),
                "lower_length": lower.get("length"),
            }
        return rows
