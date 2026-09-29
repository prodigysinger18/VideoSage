"""意图解析、工具查询与回答生成编排。"""

from __future__ import annotations

from agent.llm_client import LLMClient
from backend.agent.intent_parser import IntentParser, ParsedIntent
from backend.agent.response_generator import ResponseGenerator
from backend.agent.context_builder import build_context
from backend.agent.memory import ConversationContext, ConversationMemoryStore
from backend.agent.task_planner import build_plan
from backend.agent.state import ExecutionState
from backend.agent.validator import validate_result
from backend.agent.tool_registry import ToolRegistry
from backend.agent.tool_result import ToolResult
from backend.agent.tools.video_tool import VideoTool
from backend.agent.tools.clip_tool import ClipTool
from backend.database.connection import database


class VideoQuestionAgent:
    def __init__(self) -> None:
        self.parser = IntentParser()
        self.llm = LLMClient()
        self.generator = ResponseGenerator(self.llm)
        self.memory = ConversationMemoryStore()
        self.tools = ToolRegistry(database.get)

    def chat(self, question: str, video_id: int, conversation_id: str | None = None) -> dict:
        context = self.memory.get(conversation_id, video_id)
        intent = self._resolve_context(self.parser.parse(question), context)
        state = ExecutionState(question=question, video_id=video_id, intent=intent.name)
        tool_result = ToolResult.fail("none", "工具尚未执行")
        state.record("intent", "completed", value=intent.name)
        state.record("planning", "completed", steps=[step.name for step in build_plan(intent)])
        if intent.name in {"behavior", "outfit"} and intent.person_id is None:
            data = {}
            tool_result = ToolResult.fail("parameter_validation", "缺少 person_id")
            state.record("validate_person", "failed", error="missing person_id")
        else:
            tool_result = self._run_with_retry(intent, video_id, state)
            data = tool_result.data if tool_result.success else {}
        valid, validation_message = validate_result(intent.name, data)
        state.record("validate_result", "completed" if valid else "failed", message=validation_message)
        if not valid:
            tool_result = ToolResult.fail(tool_result.tool_name, validation_message)
            data = {}
        answer, answer_source = self.generator.generate(question, intent, data, build_context(context))
        state.record("answer", "completed", source=answer_source)
        clip_records = data
        clip_reason = intent.action or intent.event or intent.name
        if intent.name == "summary":
            clip_records = data.get("key_events", []) if isinstance(data, dict) else []
            clip_reason = "key_event"
        clips = ClipTool().build(
            video_id, clip_records, clip_reason,
            video_duration=self._video_duration(video_id),
        ) if intent.name in {"behavior", "anomaly", "summary"} else []
        state.record("clips", "completed", count=len(clips))
        self.memory.update(context, question, answer, intent.name, intent.person_id, intent.action, data)
        return {
            "conversation_id": context.conversation_id,
            "answer": answer,
            "intent": intent.name,
            "data": data,
            "evidence": tool_result.evidence,
            "clips": clips,
            "trace": state.trace,
        }

    @staticmethod
    def _video_duration(video_id: int) -> float | None:
        try:
            info = VideoTool(database.get()).get_info(video_id)
            return info.get("duration") if info else None
        except Exception:
            return None

    @staticmethod
    def _resolve_context(intent: ParsedIntent, context: ConversationContext) -> ParsedIntent:
        if intent.person_id is None:
            intent = ParsedIntent(intent.name, context.person_id, intent.action or context.action, intent.event)
        elif intent.action is None and intent.name == "behavior":
            intent = ParsedIntent(intent.name, intent.person_id, context.action, intent.event)
        return intent

    def _run_with_retry(self, intent: ParsedIntent, video_id: int, state: ExecutionState):
        last_error = None
        for attempt in range(1, 3):
            try:
                result = self.tools.execute(intent, video_id)
                if not result.success:
                    state.record("tool", "failed", name=result.tool_name, attempt=attempt, error=result.error)
                    return result
                state.record("tool", "completed", name=result.tool_name, attempt=attempt, evidence_count=len(result.evidence))
                return result
            except Exception as exc:
                last_error = exc
                state.errors.append(str(exc))
                if attempt == 1:
                    # 首次查询失败时重置连接，第二次走重新建立连接的路径。
                    database.close_current()
                state.record("tool", "retrying" if attempt == 1 else "failed", attempt=attempt, error=str(exc))
        return ToolResult.fail("tool_failed", str(last_error))
