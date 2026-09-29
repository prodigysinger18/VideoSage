"""轻量规则意图解析，不依赖 LLM。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedIntent:
    name: str
    person_id: int | None = None
    action: str | None = None
    event: str | None = None


class IntentParser:
    ACTIONS = {
        "walking": ("走路", "行走", "走动", "walking", "walk"),
        "sitting": ("坐下", "坐着", "坐姿", "sitting", "sit"),
        "standing": ("站立", "站着", "standing", "stand"),
    }

    def parse(self, question: str) -> ParsedIntent:
        text = str(question or "").strip().lower()
        person_id = self._person_id(text)
        if any(word in text for word in ("总结", "概括", "视频内容", "发生了什么", "summary")):
            return ParsedIntent("summary", person_id)
        if any(word in text for word in ("视频时长", "视频多长", "视频多久", "duration")):
            return ParsedIntent("video_info")
        if any(word in text for word in ("持续多久", "多长时间", "持续时间", "多久") ):
            return ParsedIntent("behavior", person_id)
        if any(word in text for word in ("穿搭", "衣服", "上衣", "下装", "颜色", "袖")):
            return ParsedIntent("outfit", person_id)
        if any(word in text for word in ("摔倒", "跌倒", "倒地", "fall")):
            return ParsedIntent("anomaly", person_id, event="fall")
        if any(word in text for word in ("异常", "危险", "lying", "running")):
            event = "lying" if "lying" in text else "running" if "running" in text else None
            return ParsedIntent("anomaly", person_id, event=event)
        for action, keywords in self.ACTIONS.items():
            if any(word in text for word in keywords):
                return ParsedIntent("behavior", person_id, action=action)
        if any(word in text for word in ("多少人", "人物数量", "几个人", "人数")):
            return ParsedIntent("person_count")
        if any(word in text for word in ("时长", "多长", "多久", "duration")):
            return ParsedIntent("video_info")
        return ParsedIntent("unknown", person_id)

    @staticmethod
    def _person_id(text: str) -> int | None:
        for pattern in (
            r"(?:人物|person)\s*[=:：#号]?\s*(\d+)",
            r"(\d+)\s*号(?:人物|人)?",
        ):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None
