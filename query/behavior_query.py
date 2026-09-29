"""行为时间段查询。"""

from typing import Any


class BehaviorQuery:
    def __init__(self, connection: Any, persons: Any) -> None:
        self.connection = connection
        self.persons = persons

    def get_person_behavior(self, video_id: int, person_id: int) -> list[dict]:
        database_id = self.persons.get_database_person_id(video_id, person_id)
        if database_id is None:
            return []
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """SELECT action, start_time, end_time, confidence
                   FROM dbo.behaviors WHERE person_id = ?
                   AND action IN (?, ?, ?) ORDER BY start_time""",
                (database_id, "walking", "standing", "sitting"),
            )
            return [{"action": r[0], "start_time": r[1], "end_time": r[2],
                     "confidence": r[3]} for r in cursor.fetchall()]
        finally:
            cursor.close()
