import json

from backend.api.helpers import fetch_one


class OutfitTool:
    def __init__(self, connection): self.connection = connection

    def query(self, video_id: int, person_id: int) -> dict:
        row = fetch_one(self.connection, """SELECT appearance_json FROM dbo.persons
            WHERE video_id=? AND person_id=?""", (video_id, person_id))
        if not row or not row.get("appearance_json"):
            return {}
        try:
            return json.loads(row["appearance_json"])
        except (TypeError, ValueError):
            return {}
