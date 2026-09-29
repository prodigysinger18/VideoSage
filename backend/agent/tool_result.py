"""Agent 工具统一返回结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    success: bool
    tool_name: str
    data: Any = None
    error: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def ok(cls, tool_name: str, data: Any, evidence: list[dict[str, Any]] | None = None) -> "ToolResult":
        return cls(True, tool_name, data, evidence=evidence or [])

    @classmethod
    def fail(cls, tool_name: str, error: str) -> "ToolResult":
        return cls(False, tool_name, data=None, error=error)
