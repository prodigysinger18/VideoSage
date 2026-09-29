"""本机开发环境运行器。

背景:
    默认 ``E:\\miniconda\\python.exe`` 缺少项目依赖, 而
    ``E:\\conda\\envs\\pytorch\\python.exe`` 在当前机器上存在启动异常。
    本脚本使用可用的 miniconda 解释器, 加载 pytorch conda 环境的 site-packages
    与 DLL 搜索路径后, 再执行 ``main.py``。

用法:
    E:\\miniconda\\python.exe scripts\\run_pytorch.py --no-show --max-frames 100

可通过环境变量 ``VIDEOSAGE_PYTORCH_ENV`` 覆盖 conda 环境路径。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTORCH_ENV = Path(os.environ.get("VIDEOSAGE_PYTORCH_ENV", r"E:\conda\envs\pytorch"))


def bootstrap() -> None:
    """在导入 ultralytics/cv2/torch 前配置运行环境。"""
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault(
        "YOLO_CONFIG_DIR",
        str(Path(tempfile.gettempdir()) / "videosage-ultralytics"),
    )

    sys.path.insert(0, str(PROJECT_ROOT))

    site_packages = DEFAULT_PYTORCH_ENV / "Lib" / "site-packages"
    if site_packages.is_dir():
        sys.path.insert(0, str(site_packages))

    # 注意: 本机 conda 环境与 miniconda 的 DLL 搜索顺序冲突,
    # 因此先导入 ctypes, 再注册额外的 DLL 目录。
    import ctypes  # noqa: F401

    dll_dirs = [
        DEFAULT_PYTORCH_ENV,
        DEFAULT_PYTORCH_ENV / "Library" / "bin",
        DEFAULT_PYTORCH_ENV / "Scripts",
        DEFAULT_PYTORCH_ENV / "Lib" / "site-packages" / "numpy.libs",
    ]
    for dll_dir in dll_dirs:
        if dll_dir.is_dir():
            os.add_dll_directory(str(dll_dir))


def main() -> None:
    bootstrap()

    from main import main as pipeline_main

    raise SystemExit(pipeline_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
