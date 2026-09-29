"""异常事件查询。"""

from typing import Any


class AnomalyQuery:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def get_anomaly_events(self, video_id: int) -> list[dict]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """SELECT p.person_id, a.event, a.severity, a.start_time,
                          a.end_time, a.confidence
                   FROM dbo.anomalies AS a JOIN dbo.persons AS p ON p.id = a.person_id
                   WHERE p.video_id = ? ORDER BY a.start_time, p.person_id""",
                (video_id,),
            )
            return [{"person_id": r[0], "event": r[1], "severity": r[2],
                     "start_time": r[3], "end_time": r[4], "confidence": r[5]}
                    for r in cursor.fetchall()]
        finally:
            cursor.close()
