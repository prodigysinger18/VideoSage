"""配置加载兼容入口。

当前项目的配置加载器实际位于 core/config_loader.py。
主流程第一阶段仍从 utils.config_loader 导入, 因此这里只做 re-export,
避免为了第二阶段改动无关的第一阶段导入逻辑。
"""

from core.config_loader import (
    deep_merge,
    get_section,
    get_value,
    load_config,
    resolve_path,
)

__all__ = [
    "deep_merge",
    "get_section",
    "get_value",
    "load_config",
    "resolve_path",
]
