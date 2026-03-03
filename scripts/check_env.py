#!/usr/bin/env python3
"""检查 Cloud Agent 运行环境是否就绪"""
import shutil
import sys

def check(name: str, ok: bool, msg: str = "") -> bool:
    status = "OK" if ok else "MISSING"
    print(f"  [{status}] {name}" + (f" - {msg}" if msg else ""))
    return ok

def main():
    print("=== 环境检查 ===\n")
    all_ok = True

    all_ok &= check("Python 3", sys.version_info >= (3, 8), sys.version.split()[0])
    all_ok &= check("FFmpeg", shutil.which("ffmpeg") is not None)
    try:
        __import__("requests")
        all_ok &= check("requests", True)
    except ImportError:
        all_ok &= check("requests", False)
    try:
        __import__("bs4")
        all_ok &= check("beautifulsoup4", True)
    except ImportError:
        all_ok &= check("beautifulsoup4", False)
    try:
        __import__("dashscope")
        all_ok &= check("dashscope", True)
    except ImportError:
        all_ok &= check("dashscope", False)
    try:
        __import__("PIL")
        all_ok &= check("PIL/Pillow", True)
    except ImportError:
        all_ok &= check("PIL/Pillow", False)

    import os
    has_key = bool(os.environ.get("DASHSCOPE_API_KEY"))
    all_ok &= check("DASHSCOPE_API_KEY", has_key, "需配置以生成配图" if not has_key else "已设置")

    print()
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
