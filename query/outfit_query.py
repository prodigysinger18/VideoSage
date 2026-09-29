"""从 persons.appearance_json 查询穿搭信息。"""

from typing import Any


class OutfitQuery:
    def __init__(self, connection: Any, persons: Any) -> None:
        self.connection = connection
        self.persons = persons

    def get_person_outfit(self, video_id: int, person_id: int) -> dict:
        for person in self.persons.get_persons(video_id):
            if person["person_id"] == person_id:
                appearance = person.get("appearance") or {}
                upper = appearance.get("upper") or {}
                lower = appearance.get("lower") or {}
                return {"upper_color": upper.get("color"),
                        "upper_type": upper.get("type"),
                        "lower_color": lower.get("color"),
                        "lower_type": lower.get("type"),
                        "upper_sleeve": upper.get("sleeve"),
                        "lower_length": lower.get("length"),
                        "confidence": appearance.get("confidence"),
                        "sample_count": appearance.get("sample_count")}
        return {}
