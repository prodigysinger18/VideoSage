"""人物及逻辑 person_id 映射查询。"""

import json
from typing import Any, Optional


class PersonQuery:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def get_persons(self, video_id: int) -> list[dict]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """SELECT person_id, first_seen, last_seen, appearance_json
                   FROM dbo.persons WHERE video_id = ? ORDER BY person_id""",
                (video_id,),
            )
            return [self._person(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_database_person_id(self, video_id: int, person_id: int) -> Optional[int]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT id FROM dbo.persons WHERE video_id = ? AND person_id = ?",
                (video_id, person_id),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None
        finally:
            cursor.close()

    @staticmethod
    def _person(row: Any) -> dict:
        try:
            appearance = json.loads(row[3]) if row[3] else {}
        except (TypeError, ValueError):
            appearance = {}
        return {"person_id": row[0], "appearance": appearance,
                "first_seen": row[1], "last_seen": row[2]}
