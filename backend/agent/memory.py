"""按 conversation_id 隔离的短期会话记忆。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass
class ConversationContext:
    conversation_id: str
    video_id: int | None = None
    person_id: int | None = None
    action: str | None = None
    last_intent: str = "unknown"
    time_range: tuple[float, float] | None = None
    recent_results: list[dict[str, Any]] = field(default_factory=list)
    turns: list[dict[str, str]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def reset_for_video(self, video_id: int) -> None:
        if self.video_id != video_id:
            self.video_id = video_id
            self.person_id = None
            self.action = None
            self.last_intent = "unknown"
            self.time_range = None
            self.recent_results.clear()
            self.turns.clear()


class ConversationMemoryStore:
    def __init__(self, ttl_seconds: float = 1800.0, max_sessions: int = 500, max_turns: int = 8) -> None:
        self.ttl_seconds = max(60.0, float(ttl_seconds))
        self.max_sessions = max(1, int(max_sessions))
        self.max_turns = max(2, int(max_turns))
        self._contexts: dict[str, ConversationContext] = {}
        self._lock = Lock()

    def get(self, conversation_id: str | None, video_id: int) -> ConversationContext:
        with self._lock:
            self._cleanup()
            key = conversation_id or uuid4().hex
            context = self._contexts.get(key)
            if context is None:
                if len(self._contexts) >= self.max_sessions:
                    oldest = min(self._contexts.values(), key=lambda item: item.updated_at)
                    self._contexts.pop(oldest.conversation_id, None)
                context = ConversationContext(conversation_id=key)
                self._contexts[key] = context
            context.reset_for_video(video_id)
            context.updated_at = time.time()
            return context

    def update(self, context: ConversationContext, question: str, answer: str, intent: str,
               person_id: int | None, action: str | None, data: Any) -> None:
        with self._lock:
            context.person_id = person_id if person_id is not None else context.person_id
            context.action = action if action is not None else context.action
            context.last_intent = intent
            current_range = _time_range(data)
            if current_range is not None:
                context.time_range = current_range
            context.recent_results = _result_summary(data)
            context.turns.extend(({"role": "user", "content": question}, {"role": "assistant", "content": answer}))
            context.turns[:] = context.turns[-self.max_turns:]
            context.updated_at = time.time()

    def _cleanup(self) -> None:
        deadline = time.time() - self.ttl_seconds
        expired = [key for key, context in self._contexts.items() if context.updated_at < deadline]
        for key in expired:
            self._contexts.pop(key, None)


def _time_range(data: Any) -> tuple[float, float] | None:
    if not isinstance(data, list) or not data:
        return None
    starts = [float(item["start_time"]) for item in data if isinstance(item, dict) and "start_time" in item]
    ends = [float(item["end_time"]) for item in data if isinstance(item, dict) and "end_time" in item]
    return (min(starts), max(ends)) if starts and ends else None


def _result_summary(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [dict(item) for item in data[:5] if isinstance(item, dict)]
    return [dict(data)] if isinstance(data, dict) and data else []
