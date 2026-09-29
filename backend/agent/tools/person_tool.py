from backend.api.helpers import fetch_one


class PersonTool:
    def __init__(self, connection): self.connection = connection

    def count(self, video_id: int) -> dict:
        row = fetch_one(self.connection, "SELECT COUNT(*) AS person_count FROM dbo.persons WHERE video_id=?", (video_id,)) or {}
        return {"person_count": int(row.get("person_count") or 0)}
