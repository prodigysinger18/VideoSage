"""把意图转换为可执行步骤。"""

from __future__ import annotations

from dataclasses import dataclass

from backend.agent.intent_parser import ParsedIntent


@dataclass(frozen=True)
class PlanStep:
    name: str
    tool: str | None = None
    required: bool = True


def build_plan(intent: ParsedIntent) -> list[PlanStep]:
    if intent.name == "unknown":
        return [PlanStep("clarify")]
    if intent.name == "behavior":
        return [PlanStep("validate_person", required=True), PlanStep("query_behavior", "behavior_tool.query"), PlanStep("validate_result")]
    if intent.name == "outfit":
        return [PlanStep("validate_person", required=True), PlanStep("query_outfit", "outfit_tool.query"), PlanStep("validate_result")]
    if intent.name == "anomaly":
        return [PlanStep("query_anomaly", "anomaly_tool.query"), PlanStep("validate_result")]
    if intent.name == "video_info":
        return [PlanStep("query_video", "video_tool.get_info"), PlanStep("validate_result")]
    if intent.name == "person_count":
        return [PlanStep("query_person_count", "person_tool.count"), PlanStep("validate_result")]
    if intent.name == "summary":
        return [PlanStep("query_summary", "summary_tool.query"), PlanStep("validate_result")]
    return [PlanStep("clarify")]
