from backend.api.helpers import fetch_all


class BehaviorTool:
    def __init__(self, connection): self.connection = connection

    def query(self, video_id: int, person_id: int, action: str) -> list[dict]:
        rows = fetch_all(self.connection, """SELECT b.action,b.start_time,b.end_time,b.confidence
            FROM dbo.behaviors b JOIN dbo.persons p ON p.id=b.person_id
            WHERE p.video_id=? AND p.person_id=? AND b.action=? ORDER BY b.start_time""", (video_id, person_id, action))
        for row in rows:
            row["duration"] = round(float(row["end_time"]) - float(row["start_time"]), 4)
        return rows
