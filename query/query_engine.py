"""面向调用方的统一查询入口。"""

from typing import Optional

from query.database import QueryDatabase
from query.video_query import VideoQuery
from query.person_query import PersonQuery
from query.behavior_query import BehaviorQuery
from query.outfit_query import OutfitQuery
from query.anomaly_query import AnomalyQuery


class QueryEngine:
    def __init__(self, config_path: Optional[str] = None) -> None:
        self.database = QueryDatabase(config_path)
        connection = self.database.get_connection()
        self.persons = PersonQuery(connection)
        self.videos = VideoQuery(connection)
        self.behaviors = BehaviorQuery(connection, self.persons)
        self.outfits = OutfitQuery(connection, self.persons)
        self.anomalies = AnomalyQuery(connection)

    def get_video_info(self, video_id: int):
        return self.videos.get_video_info(video_id)

    def get_persons(self, video_id: int):
        return self.persons.get_persons(video_id)

    def get_behavior(self, video_id: int, person_id: int):
        return self.behaviors.get_person_behavior(video_id, person_id)

    def get_outfit(self, video_id: int, person_id: int):
        return self.outfits.get_person_outfit(video_id, person_id)

    def get_anomaly(self, video_id: int):
        return self.anomalies.get_anomaly_events(video_id)

    def close(self) -> None:
        self.database.close_connection()

    def __enter__(self) -> "QueryEngine":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
