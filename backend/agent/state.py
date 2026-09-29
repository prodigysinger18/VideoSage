"""Agent 执行状态与短期上下文。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionState:
    question: str
    video_id: int
    intent: str = "unknown"
    status: str = "created"
    current_step: str = ""
    attempts: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)

    def record(self, step: str, status: str, **details: Any) -> None:
        self.current_step = step
        self.status = status
        self.trace.append({"step": step, "status": status, **details})
