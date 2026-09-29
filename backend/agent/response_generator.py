"""将工具结果转换为最终自然语言回答。"""

from __future__ import annotations

import json
from typing import Any

from agent.llm_client import LLMClient
from backend.agent.intent_parser import ParsedIntent


class ResponseGenerator:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def generate(self, question: str, intent: ParsedIntent, data: Any, context: dict | None = None) -> tuple[str, str]:
        fallback = self._fallback(intent, data)
        if intent.name == "unknown" or not data:
            return fallback, "rule_fallback"
        try:
            answer = self.llm.chat([
                {"role": "system", "content": "你是VideoSage视频分析助手。只根据工具结果回答，使用简洁中文，保留人物编号和秒数，不得虚构。"},
                {"role": "user", "content": f"对话上下文：{json.dumps(context or {}, ensure_ascii=False, default=str)}\n问题：{question}\n工具结果：{json.dumps(data, ensure_ascii=False, default=str)}"},
            ])
            return answer, "llm"
        except Exception:
            return fallback, "rule_fallback"

    @staticmethod
    def _fallback(intent: ParsedIntent, data: Any) -> str:
        if intent.name == "unknown":
            return "暂时无法识别问题。可以询问视频时长、人物数量、行为、异常或穿搭。"
        if intent.person_id is None and intent.name in {"behavior", "outfit"}:
            return "请在问题中指定人物编号，例如“人物1什么时候开始走路”。"
        if not data:
            return "没有查询到符合条件的分析结果。"
        if intent.name == "video_info":
            return f"视频时长为 {data.get('duration')} 秒，分辨率为 {data.get('width')}×{data.get('height')}。"
        if intent.name == "person_count":
            return f"视频中记录了 {data.get('person_count', 0)} 个人物。"
        if intent.name == "summary":
            video = data.get("video") or {}
            events = data.get("key_events") or []
            event_text = "、".join(str(item.get("event")) for item in events[:5]) or "暂无异常事件"
            return f"视频《{video.get('video_name', '')}》时长约{video.get('duration', 0)}秒，共记录{data.get('person_count', 0)}个人物，检测到的重点事件包括：{event_text}。"
        if intent.name == "behavior":
            total = sum(float(item.get("duration") or 0) for item in data)
            times = "、".join(f"{item['start_time']}至{item['end_time']}秒" for item in data)
            return f"人物{intent.person_id}的{intent.action}行为出现在：{times}，累计约{total:.1f}秒。"
        if intent.name == "anomaly":
            descriptions = []
            for item in data[:10]:
                outfit = item.get("outfit") or {}
                clothing = _clothing_text(outfit)
                person = f"人物{item.get('person_id')}"
                event = _event_text(item.get("event"))
                time_text = f"{item.get('start_time')}至{item.get('end_time')}秒"
                descriptions.append(f"{person}{clothing}在{time_text}发生{event}")
            return "；".join(descriptions) + "。"
        return f"人物{intent.person_id}的穿搭信息为：{json.dumps(data, ensure_ascii=False)}"


def _clothing_text(outfit: dict) -> str:
    upper_color = outfit.get("upper_color")
    upper_type = outfit.get("upper_type")
    lower_color = outfit.get("lower_color")
    lower_type = outfit.get("lower_type")
    parts = []
    if upper_color or upper_type:
        parts.append(f"穿{upper_color or '未知颜色'}{_type_text(upper_type, '上衣')}")
    if lower_color or lower_type:
        parts.append(f"配{lower_color or '未知颜色'}{_type_text(lower_type, '下装')}")
    return "（" + "、".join(parts) + "）" if parts else ""


def _type_text(value: str | None, default: str) -> str:
    if not value:
        return default
    return {"short_sleeve_top": "短袖", "long_sleeve_top": "长袖", "pants": "长裤", "skirt": "裙子"}.get(value, value)


def _event_text(value: str | None) -> str:
    return {
        "fall": "摔倒",
        "lying": "倒地",
        "running": "奔跑",
        "sudden_down": "突然倒下",
        "abnormal_movement": "异常移动",
    }.get(value, value or "异常行为")
