"""OpenAI 兼容 API 客户端。"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from core.config_loader import get_section, load_config


class LLMClient:
    def __init__(self, config_path: Optional[str] = None) -> None:
        config = get_section(load_config(config_path), "llm")
        self.enabled = bool(config.get("enabled", False))
        self.api_key = str(config.get("api_key") or "")
        self.base_url = str(config.get("base_url") or "") or None
        self.model = str(config.get("model") or "")
        self._client: Any = None

    def chat(self, messages: Sequence[dict[str, str]]) -> str:
        if not self.enabled:
            raise RuntimeError("LLM 功能未启用")
        if not self.api_key or not self.model:
            raise RuntimeError("LLM api_key 或 model 未配置")
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("当前环境未安装 OpenAI SDK") from exc
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=list(messages),
            temperature=0.1,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("LLM 返回了空回答")
        return str(content).strip()
