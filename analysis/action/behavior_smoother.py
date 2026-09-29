"""逐帧行为平滑。

使用每个 person_id 独立的滑动窗口多数投票, 消除单帧抖动。
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Any, Deque, Dict, List, Tuple


class BehaviorSmoother:
    """滑动窗口多数投票平滑器。"""

    def __init__(self, window_size: int = 7, switch_confirmations: int = 3) -> None:
        self.window_size = max(3, int(window_size))
        self.switch_confirmations = max(2, int(switch_confirmations))
        self._histories: Dict[int, Deque[Tuple[float, str, float]]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )
        self._last_smoothed: Dict[int, str] = {}
        self._candidates: Dict[int, Tuple[str, int]] = {}

    def update(
        self,
        person_id: int,
        timestamp: float,
        action: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """加入一帧原始结果, 返回平滑后的行为。"""
        history = self._histories[person_id]
        history.append((float(timestamp), str(action), float(confidence)))

        if len(history) < self.switch_confirmations:
            smoothed_action = "unknown"
            stabilized = False
        else:
            counter = Counter(item[1] for item in list(history)[-self.window_size :])
            top_action, top_count = counter.most_common(1)[0]
            required_votes = max(self.switch_confirmations, len(history) // 2 + 1)
            previous = self._last_smoothed.get(person_id, "unknown")
            if top_action == previous:
                smoothed_action = previous
                self._candidates.pop(person_id, None)
            elif top_count >= required_votes:
                candidate, count = self._candidates.get(person_id, (top_action, 0))
                count = count + 1 if candidate == top_action else 1
                self._candidates[person_id] = (top_action, count)
                smoothed_action = top_action if count >= self.switch_confirmations else previous
            else:
                self._candidates.pop(person_id, None)
                smoothed_action = previous
            stabilized = smoothed_action != "unknown"

        self._last_smoothed[person_id] = smoothed_action

        matched = [item for item in history if item[1] == smoothed_action]
        average_confidence = (
            sum(item[2] for item in matched) / len(matched) if matched else float(confidence)
        )

        return {
            "person_id": int(person_id),
            "timestamp": float(timestamp),
            "action": smoothed_action,
            "confidence": round(float(average_confidence), 4),
            "stabilized": stabilized,
        }

    def last_action(self, person_id: int) -> str:
        """获取该人物最近一次平滑结果。"""
        return self._last_smoothed.get(person_id, "unknown")
