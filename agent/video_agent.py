"""查询引擎与 LLM 的统一编排。"""

from __future__ import annotations

import json
from typing import Any, Optional

from agent.intent_router import IntentResult, IntentRouter
from agent.llm_client import LLMClient
from query.query_engine import QueryEngine


class VideoAgent:
    def __init__(self, config_path: Optional[str] = None) -> None:
        self.query_engine = QueryEngine(config_path)
        self.llm = LLMClient(config_path)
        self.router = IntentRouter()

    def chat(self, question: str, video_id: int) -> dict[str, Any]:
        route = self.router.route(question)
        if route.intent == "unknown":
            return {"answer": "暂时无法识别该问题，请询问视频信息、人物行为、穿搭或异常事件。", "intent": "unknown", "data": {}}

        data, error = self._query(route, int(video_id))
        if error:
            return {"answer": error, "intent": route.intent, "data": data}
        if not data:
            return {"answer": "没有查询到符合条件的分析结果。", "intent": route.intent, "data": data}

        fallback = self._fallback_answer(route, data)
        try:
            answer = self.llm.chat(
                [
                    {"role": "system", "content": "你是视频分析助手。只能根据给定查询结果简洁回答，不得补充未提供的事实。"},
                    {"role": "user", "content": f"问题：{question}\n查询结果：{json.dumps(data, ensure_ascii=False)}"},
                ]
            )
        except Exception:
            answer = fallback
        return {"answer": answer, "intent": route.intent, "data": data}

    def _query(self, route: IntentResult, video_id: int) -> tuple[Any, Optional[str]]:
        if route.intent == "video_info":
            return self.query_engine.get_video_info(video_id), None
        if route.intent == "anomaly":
            records = self.query_engine.get_anomaly(video_id)
            if route.person_id is not None:
                records = [item for item in records if item.get("person_id") == route.person_id]
            return records, None
        if route.person_id is None:
            return {}, "该问题需要指定人物编号，例如“2号人物什么时候开始走路”。"
        if route.intent == "outfit":
            return self.query_engine.get_outfit(video_id, route.person_id), None
        records = self.query_engine.get_behavior(video_id, route.person_id)
        if route.action:
            records = [item for item in records if item.get("action") == route.action]
        return records, None

    @staticmethod
    def _fallback_answer(route: IntentResult, data: Any) -> str:
        if route.intent == "video_info":
            return f"视频信息：{json.dumps(data, ensure_ascii=False)}"
        if route.intent == "outfit":
            return f"该人物的穿搭分析结果为：{json.dumps(data, ensure_ascii=False)}"
        if route.intent == "anomaly":
            return f"共查询到 {len(data)} 条异常事件。"
        return f"共查询到 {len(data)} 个相关行为时间段。"

    def close(self) -> None:
        self.query_engine.close()

    def __enter__(self) -> "VideoAgent":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
