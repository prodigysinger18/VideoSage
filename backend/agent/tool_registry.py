"""集中注册并执行 Agent 可用工具。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.agent.intent_parser import ParsedIntent
from backend.agent.tool_result import ToolResult
from backend.agent.tools.anomaly_tool import AnomalyTool
from backend.agent.tools.behavior_tool import BehaviorTool
from backend.agent.tools.outfit_tool import OutfitTool
from backend.agent.tools.person_tool import PersonTool
from backend.agent.tools.video_tool import VideoTool
from backend.agent.tools.summary_tool import SummaryTool


class ToolRegistry:
    def __init__(self, connection_provider: Callable[[], Any]) -> None:
        self.connection_provider = connection_provider
        self._executors = {
            "video_info": self._video_info,
            "person_count": self._person_count,
            "behavior": self._behavior,
            "anomaly": self._anomaly,
            "outfit": self._outfit,
            "summary": self._summary,
        }

    @property
    def names(self) -> list[str]:
        return sorted(self._executors)

    def execute(self, intent: ParsedIntent, video_id: int) -> ToolResult:
        executor = self._executors.get(intent.name)
        if executor is None:
            return ToolResult.fail("none", f"未注册意图工具：{intent.name}")
        return executor(intent, video_id)

    def _video_info(self, intent: ParsedIntent, video_id: int) -> ToolResult:
        data = VideoTool(self.connection_provider()).get_info(video_id)
        return ToolResult.ok("video_tool.get_info", data, _dict_evidence("dbo.videos", data))

    def _person_count(self, intent: ParsedIntent, video_id: int) -> ToolResult:
        data = PersonTool(self.connection_provider()).count(video_id)
        return ToolResult.ok("person_tool.count", data, _dict_evidence("dbo.persons", data))

    def _behavior(self, intent: ParsedIntent, video_id: int) -> ToolResult:
        if intent.person_id is None or not intent.action:
            return ToolResult.fail("behavior_tool.query", "缺少 person_id 或 action")
        data = BehaviorTool(self.connection_provider()).query(video_id, intent.person_id, intent.action)
        return ToolResult.ok("behavior_tool.query", data, _list_evidence("dbo.behaviors", data))

    def _anomaly(self, intent: ParsedIntent, video_id: int) -> ToolResult:
        data = AnomalyTool(self.connection_provider()).query(video_id, intent.person_id, intent.event)
        return ToolResult.ok("anomaly_tool.query", data, _list_evidence("dbo.anomalies", data))

    def _outfit(self, intent: ParsedIntent, video_id: int) -> ToolResult:
        if intent.person_id is None:
            return ToolResult.fail("outfit_tool.query", "缺少 person_id")
        data = OutfitTool(self.connection_provider()).query(video_id, intent.person_id)
        return ToolResult.ok("outfit_tool.query", data, _dict_evidence("dbo.persons.appearance_json", data))

    def _summary(self, intent: ParsedIntent, video_id: int) -> ToolResult:
        data = SummaryTool(self.connection_provider()).query(video_id, intent.person_id)
        return ToolResult.ok("summary_tool.query", data, _dict_evidence("dbo.videos+analysis_results", data))


def _dict_evidence(source: str, data: dict) -> list[dict]:
    return [{"source": source, "record": data}] if data else []


def _list_evidence(source: str, data: list[dict]) -> list[dict]:
    return [{"source": source, "record": record} for record in data[:20]]
