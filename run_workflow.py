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


def stage_scrape() -> tuple[list[dict], Path | None]:
    """返回 (全部条目, 抓取文件路径)。视频阶段只取前 MAX_ITEMS 条。"""
    print("=== 阶段1: 信息抓取 ===")
    if not run([sys.executable, ".cursor/skills/embodied-ai-research/scripts/scrape_sources.py"]):
        return [], None

    scraped_dir = PROJECT_ROOT / "outputs" / "scraped"
    files = sorted(scraped_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print("无抓取结果", file=sys.stderr)
        return [], None

    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    if not items:
        print("无有效条目", file=sys.stderr)
    return items, files[0]


def stage_report(all_items: list[dict], scraped_file: Path) -> Path | None:
    """阶段1.5: 生成今日报告。"""
    print(f"\n=== 阶段1.5: 生成今日报告 ({len(all_items)} 条信息) ===")
    report_dir = PROJECT_ROOT / "outputs" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"report_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"

    if run([sys.executable, "scripts/generate_report.py",
            str(scraped_file), "--output", str(report_path)]):
        return report_path
    return None


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


def stage_realvideo(items: list[dict], drafts: Path) -> Path | None:
    """实拍素材+配音模式。"""
    print("\n=== 阶段2: 实拍素材+配音视频生成 ===")
    items_file = drafts / "realvideo_items.json"
    with open(items_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    out_video = drafts / f"realvideo_{datetime.now().strftime('%H%M')}.mp4"
    if run([sys.executable, "scripts/realvideo_pipeline.py",
            str(items_file), "--output", str(out_video)]):
        return out_video
    return None


def main():
    legacy_mode = "--legacy" in sys.argv
    realvideo_mode = "--real" in sys.argv

    all_items, scraped_file = stage_scrape()
    if not all_items:
        return 1

    report_path = stage_report(all_items, scraped_file)
    if report_path:
        print(f"报告已生成: {report_path}")

    video_items = all_items[:MAX_ITEMS]
    drafts = PROJECT_ROOT / "outputs" / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)

    if realvideo_mode:
        out = stage_realvideo(video_items, drafts)
    elif legacy_mode:
        out = stage_legacy(video_items, drafts)
    else:
        img_dir = stage_generate_images(video_items, drafts)
        out = stage_video_template(video_items, img_dir, drafts)

    if out:
        print(f"\n完成: {out}")
        if report_path:
            print(f"报告: {report_path}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
