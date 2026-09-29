"""VideoSage 环境自检脚本。

用途:
    确认第一阶段所需依赖(OpenCV / PyTorch / Ultralytics / PyYAML / SciPy)与 GPU 是否可用,
    并打印可复现的环境信息, 作为性能记录的基础。

运行:
    E:\conda\envs\pytorch\python.exe scripts\check_env.py
"""

import os
import platform
import sys

# libiomp5md.dll 冲突(OpenMP Error #15)的规避开关, 必须在导入 torch 之前设置
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")


def _version(module_name):
    try:
        module = __import__(module_name)
    except Exception as exc:  # pragma: no cover - 仅用于环境自检
        return f"缺失 ({type(exc).__name__}: {exc})"
    return getattr(module, "__version__", "unknown")


def collect():
    """收集环境信息, 返回 dict。"""
    info = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "opencv": _version("cv2"),
        "numpy": _version("numpy"),
        "pyyaml": _version("yaml"),
        "scipy": _version("scipy"),
        "torch": _version("torch"),
        "ultralytics": _version("ultralytics"),
    }

    try:
        import torch

        info["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["cuda_version"] = torch.version.cuda
            info["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["gpu_total_memory_mb"] = round(props.total_memory / 1024 ** 2, 1)
            free_mb, total_mb = (
                value / 1024 ** 2 for value in torch.cuda.mem_get_info()
            )
            info["gpu_free_memory_mb"] = round(free_mb, 1)
    except Exception as exc:  # pragma: no cover
        info["cuda_available"] = f"检查失败 ({type(exc).__name__}: {exc})"

    return info


def main():
    info = collect()
    width = max(len(key) for key in info)
    print("=" * 60)
    print("VideoSage 环境自检")
    print("=" * 60)
    for key, value in info.items():
        print(f"{key:<{width}} : {value}")
    print("=" * 60)


if __name__ == "__main__":
    main()
