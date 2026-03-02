#!/usr/bin/env python3
"""
运行完整工作流：抓取 -> 生图 -> 剪辑
供 Cloud Agent 或本地执行。
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], cwd: Path = PROJECT_ROOT) -> bool:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return False
    if r.stdout:
        print(r.stdout.strip())
    return True


def main():
    print("=== 阶段1: 信息抓取 ===")
    if not run([sys.executable, ".cursor/skills/embodied-ai-research/scripts/scrape_sources.py"]):
        return 1

    scraped_dir = PROJECT_ROOT / "outputs" / "scraped"
    files = sorted(scraped_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print("无抓取结果", file=sys.stderr)
        return 1

    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])[:1]
    if not items:
        print("无有效条目", file=sys.stderr)
        return 1

    item = items[0]
    title = item.get("title", "具身智能")
    print(f"选中: {title}")

    print("\n=== 阶段2a: 生成配图 ===")
    drafts = PROJECT_ROOT / "outputs" / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    img_path = drafts / "workflow_illustration.png"
    if not run([sys.executable, ".cursor/skills/image-gen-blotato/scripts/generate_image.py",
                title, "--output", str(img_path)]):
        return 1

    print("\n=== 阶段2b: 视频剪辑 ===")
    base_video = drafts / "test_input.mp4"
    if not base_video.exists():
        print("创建基础视频...")
        subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "color=c=blue:s=720x1280:d=3",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", str(base_video), "-y"],
                      cwd=PROJECT_ROOT, capture_output=True, check=True)

    instr = {
        "ops": [
            {"type": "concat", "inputs": [str(base_video)]},
            {"type": "watermark", "text": "@具身智能"},
            {"type": "export", "format": "mp4", "resolution": "720x1280"}
        ]
    }
    instr_path = drafts / "workflow_instructions.json"
    with open(instr_path, "w", encoding="utf-8") as f:
        json.dump(instr, f, ensure_ascii=False, indent=2)

    out_video = drafts / f"workflow_draft_{datetime.now().strftime('%H%M')}.mp4"
    if not run([sys.executable, ".cursor/skills/video-processing/scripts/process_video.py",
                str(instr_path), "--output", str(out_video)]):
        return 1

    print(f"\n完成: {out_video}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
