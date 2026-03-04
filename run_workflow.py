#!/usr/bin/env python3
"""
运行完整工作流：抓取 -> 多条生图 -> 新闻合辑视频
供 Cloud Agent 或本地执行。
支持 --legacy 回退到旧版单条视频模式。
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MAX_ITEMS = 5


def run(cmd: list[str], cwd: Path = PROJECT_ROOT) -> bool:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.stderr:
        print(r.stderr.strip(), file=sys.stderr)
    if r.returncode != 0:
        return False
    if r.stdout:
        print(r.stdout.strip())
    return True


def stage_scrape() -> list[dict]:
    print("=== 阶段1: 信息抓取 ===")
    if not run([sys.executable, ".cursor/skills/embodied-ai-research/scripts/scrape_sources.py"]):
        return []

    scraped_dir = PROJECT_ROOT / "outputs" / "scraped"
    files = sorted(scraped_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print("无抓取结果", file=sys.stderr)
        return []

    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])[:MAX_ITEMS]
    if not items:
        print("无有效条目", file=sys.stderr)
    return items


def stage_generate_images(items: list[dict], drafts: Path) -> Path:
    img_dir = drafts / "illustrations"
    img_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== 阶段2a: 为 {len(items)} 条新闻生成配图 ===")
    for i, item in enumerate(items):
        idx = i + 1
        title = item.get("title", "具身智能")
        img_path = img_dir / f"illustration_{idx}.png"
        print(f"  [{idx}/{len(items)}] {title[:40]}...")
        run([sys.executable, ".cursor/skills/image-gen-blotato/scripts/generate_image.py",
             title, "--output", str(img_path)])
    return img_dir


def stage_video_template(items: list[dict], img_dir: Path, drafts: Path) -> Path | None:
    print("\n=== 阶段2b: 生成新闻合辑视频 ===")
    items_file = drafts / "template_items.json"
    with open(items_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    out_video = drafts / f"news_{datetime.now().strftime('%H%M')}.mp4"
    if run([sys.executable, ".cursor/skills/video-processing/scripts/video_template.py",
            str(items_file), "--output", str(out_video), "--image-dir", str(img_dir)]):
        return out_video
    return None


def stage_legacy(items: list[dict], drafts: Path) -> Path | None:
    """旧版单条模式，保持向后兼容。"""
    item = items[0]
    title = item.get("title", "具身智能")
    print(f"选中: {title}")

    print("\n=== 阶段2a: 生成配图 ===")
    img_path = drafts / "workflow_illustration.png"
    if not run([sys.executable, ".cursor/skills/image-gen-blotato/scripts/generate_image.py",
                title, "--output", str(img_path)]):
        return None

    print("\n=== 阶段2b: 视频剪辑 ===")
    base_video = drafts / "test_input.mp4"
    if not base_video.exists():
        print("创建基础视频...")
        subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "color=c=blue:s=720x1280:d=3",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", str(base_video), "-y"],
                      cwd=PROJECT_ROOT, capture_output=True, check=True)

    ops = [{"type": "concat", "inputs": [str(base_video)]}]
    if img_path.exists():
        ops.append({"type": "overlay", "image": str(img_path), "position": "center"})
    ops.append({"type": "watermark", "text": "@具身智能"})
    ops.append({"type": "export", "format": "mp4", "resolution": "720x1280"})
    instr = {"ops": ops}
    instr_path = drafts / "workflow_instructions.json"
    with open(instr_path, "w", encoding="utf-8") as f:
        json.dump(instr, f, ensure_ascii=False, indent=2)

    out_video = drafts / f"workflow_draft_{datetime.now().strftime('%H%M')}.mp4"
    if run([sys.executable, ".cursor/skills/video-processing/scripts/process_video.py",
            str(instr_path), "--output", str(out_video)]):
        return out_video
    return None


def main():
    legacy_mode = "--legacy" in sys.argv
    items = stage_scrape()
    if not items:
        return 1

    drafts = PROJECT_ROOT / "outputs" / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)

    if legacy_mode:
        out = stage_legacy(items, drafts)
    else:
        img_dir = stage_generate_images(items, drafts)
        out = stage_video_template(items, img_dir, drafts)

    if out:
        print(f"\n完成: {out}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
