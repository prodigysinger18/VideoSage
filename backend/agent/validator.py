"""对工具输出做最小结构校验，防止回答建立在错误数据上。"""

from __future__ import annotations

from typing import Any


def validate_result(intent: str, data: Any) -> tuple[bool, str]:
    if intent in {"behavior", "anomaly"}:
        if not isinstance(data, list):
            return False, "查询结果不是列表"
        for item in data:
            if not isinstance(item, dict) or "start_time" not in item or "end_time" not in item:
                return False, "时间段字段不完整"
            if float(item["end_time"]) < float(item["start_time"]):
                return False, "时间段结束时间早于开始时间"
        return True, "ok"
    if intent == "video_info":
        return isinstance(data, dict) and bool(data), "视频信息为空" if not data else "ok"
    if intent == "person_count":
        valid = isinstance(data, dict) and isinstance(data.get("person_count"), int)
        return valid, "人物数量字段无效" if not valid else "ok"
    if intent == "outfit":
        return isinstance(data, dict), "穿搭结果不是对象" if not isinstance(data, dict) else "ok"
    if intent == "summary":
        valid = isinstance(data, dict) and isinstance(data.get("persons"), list)
        return valid, "摘要结构无效" if not valid else "ok"
    return True, "ok"
