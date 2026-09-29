"""基于规则的视频问题意图识别。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IntentResult:
    intent: str
    person_id: Optional[int] = None
    action: Optional[str] = None


class IntentRouter:
    _ACTION_KEYWORDS = {
        "walking": ("走路", "行走", "走动", "walking", "walk"),
        "standing": ("站立", "站着", "standing", "stand"),
        "sitting": ("坐下", "坐着", "坐姿", "sitting", "sit"),
    }

    def route(self, question: str) -> IntentResult:
        normalized = str(question or "").strip().lower()
        person_id = self._extract_person_id(normalized)
        if any(word in normalized for word in ("摔倒", "异常", "危险", "倒地", "fall", "anomaly")):
            return IntentResult("anomaly", person_id)
        if any(word in normalized for word in ("穿什么", "穿着", "衣服", "穿搭", "上衣", "下装", "outfit")):
            return IntentResult("outfit", person_id)
        for action, keywords in self._ACTION_KEYWORDS.items():
            if any(word in normalized for word in keywords):
                return IntentResult("behavior", person_id, action)
        if any(word in normalized for word in ("视频信息", "时长", "分辨率", "帧率", "fps", "video")):
            return IntentResult("video_info", person_id)
        return IntentResult("unknown", person_id)

    @staticmethod
    def _extract_person_id(question: str) -> Optional[int]:
        patterns = (
            r"(?:person[_\s-]*id|person|人物|人员|人)\s*[=:：#号]?\s*(\d+)",
            r"(\d+)\s*号(?:人物|人员|人)?",
        )
        for pattern in patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None
