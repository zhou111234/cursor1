#!/usr/bin/env python3
"""
视频模板引擎 v2：仿抖音 AI 测评类短视频风格。
特点：渐变背景、大字钩子、圆形编号、彩色关键词、快节奏、白闪转场。
结构：钩子片头(2s) → 多条新闻(每条4s) → 总结片尾(3s)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

WIDTH, HEIGHT = 720, 1280
FPS = 25
FONT = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
FONT_FALLBACK = "WenQuanYi Micro Hei"


def _run_ff(args: list[str], label: str = "") -> bool:
    cmd = ["ffmpeg", "-y"] + args
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error ({label}): {e.stderr.decode()[:500]}", file=sys.stderr)
        return False


def _fa() -> str:
    if Path(FONT).exists():
        return f"fontfile={FONT}"
    return f"font={FONT_FALLBACK}"


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace('"', '\\"')


def _wrap(text: str, max_chars: int = 14) -> str:
    lines = []
    while len(text) > max_chars:
        lines.append(text[:max_chars])
        text = text[max_chars:]
    if text:
        lines.append(text)
    return "\n".join(lines)


def _gradient_bg(duration: float) -> str:
    """紫蓝渐变背景 (通过两色条叠加模拟)。"""
    return (
        f"color=c=0x1a0533:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}[_bg0];"
        f"color=c=0x0a2a5c:s={WIDTH}x{HEIGHT//2}:d={duration}:r={FPS}[_bg1];"
        f"[_bg0][_bg1]overlay=0:{HEIGHT//2}[_bgbase];"
        f"color=c=0x6c3baa@0.15:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}[_glow];"
        f"[_bgbase][_glow]overlay=0:0[_grad]"
    )


def generate_hook(output: str, title: str, channel: str = "@具身智能",
                  duration: float = 2.5) -> bool:
    """钩子片头：超大黄色标题 + 日期标签 + 频道名。"""
    fa = _fa()
    date_tag = datetime.now().strftime("%m.%d")
    hook_title = _wrap(title, max_chars=10)
    escaped_title = _esc(hook_title)
    escaped_channel = _esc(channel)

    filters = [
        _gradient_bg(duration),
        f"color=c=0xffc107:s=180x6:d={duration}:r={FPS}[_bar]",
        f"[_grad][_bar]overlay=(w-180)/2:160[b1]",
        (
            f"[b1]drawtext={fa}:text='🤖 具身智能快讯':"
            f"fontsize=30:fontcolor=0xffc107:"
            f"x=(w-text_w)/2:y=110:"
            f"enable='gte(t,0.1)'[t0]"
        ),
        (
            f"[t0]drawtext={fa}:text='{date_tag}':"
            f"fontsize=26:fontcolor=white:"
            f"x=(w-text_w)/2:y=180:"
            f"enable='gte(t,0.2)'[t1]"
        ),
        (
            f"[t1]drawtext={fa}:text='{escaped_title}':"
            f"fontsize=60:fontcolor=0xffc107:"
            f"line_spacing=16:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-80:"
            f"enable='gte(t,0.3)'[t2]"
        ),
        (
            f"[t2]drawtext={fa}:text='👇 今日必看 👇':"
            f"fontsize=32:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h)/2+100:"
            f"enable='gte(t,0.6)'[t3]"
        ),
        f"color=c=0x000000@0.7:s={WIDTH}x70:d={duration}:r={FPS}[_hookbar]",
        f"[t3][_hookbar]overlay=0:{HEIGHT-70}[t4]",
        (
            f"[t4]drawtext={fa}:text='2分钟看完今日具身智能大事 | {escaped_channel}':"
            f"fontsize=24:fontcolor=white:"
            f"x=(w-text_w)/2:y={HEIGHT-50}:"
            f"enable='gte(t,0.5)'[out]"
        ),
    ]

    args = [
        "-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01",
        "-filter_complex", ";".join(filters),
        "-map", "[out]", "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        output,
    ]
    return _run_ff(args, "hook")


def generate_news_card(
    output: str,
    index: int,
    title: str,
    source: str,
    image_path: Optional[str] = None,
    duration: float = 4.0,
) -> bool:
    """新闻卡片：渐变背景 + 圆形编号 + 配图 + 大标题 + 来源。"""
    fa = _fa()
    circle_nums = ["❶", "❷", "❸", "❹", "❺", "❻", "❼", "❽", "❾", "❿"]
    num_char = circle_nums[index - 1] if index <= len(circle_nums) else f"#{index}"
    wrapped = _wrap(title, max_chars=14)
    e_title = _esc(wrapped)
    e_source = _esc(source)
    e_num = _esc(num_char)

    img_size = 440
    img_x = (WIDTH - img_size) // 2
    img_y = 170
    border_w = 4

    if image_path and Path(image_path).exists():
        filter_parts = [
            _gradient_bg(duration),
            f"color=c=0x00e5ff:s={img_size+border_w*2}x{img_size+border_w*2}:d={duration}:r={FPS}[_border]",
            f"[_grad][_border]overlay={img_x-border_w}:{img_y-border_w}[_b0]",
            (
                f"[1:v]scale={img_size}:{img_size}:force_original_aspect_ratio=decrease,"
                f"pad={img_size}:{img_size}:(ow-iw)/2:(oh-ih)/2:color=0x0a0a2a,"
                f"format=rgba[_img]"
            ),
            f"[_b0][_img]overlay={img_x}:{img_y}[b0]",
        ]
        input_args = ["-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01", "-i", image_path]
    else:
        filter_parts = [_gradient_bg(duration)]
        filter_parts.append(f"[_grad]null[b0]")
        input_args = ["-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01"]

    y_title = img_y + img_size + 40 if image_path and Path(image_path).exists() else 350

    filter_parts.extend([
        (
            f"[b0]drawtext={fa}:text='{e_num}':"
            f"fontsize=72:fontcolor=0xffc107:"
            f"x=40:y=60:"
            f"enable='gte(t,0.1)'[n1]"
        ),
        f"color=c=0xffc107:s=4x50:d={duration}:r={FPS}[_vbar]",
        f"[n1][_vbar]overlay=120:70[n2]",
        (
            f"[n2]drawtext={fa}:text='具身智能':"
            f"fontsize=24:fontcolor=0xbb86fc:"
            f"x=140:y=70:"
            f"enable='gte(t,0.1)'[n3]"
        ),
        (
            f"[n3]drawtext={fa}:text='{e_title}':"
            f"fontsize=44:fontcolor=white:"
            f"line_spacing=10:"
            f"x=(w-text_w)/2:y={y_title}:"
            f"enable='gte(t,0.2)'[n4]"
        ),
        f"color=c=0x000000@0.55:s={WIDTH}x120:d={duration}:r={FPS}[_bot]",
        f"[n4][_bot]overlay=0:{HEIGHT-120}[n5]",
        f"color=c=0x0088ff:s=200x40:d={duration}:r={FPS}[_tag]",
        f"[n5][_tag]overlay=20:{HEIGHT-110}[n6]",
        (
            f"[n6]drawtext={fa}:text='具身智能快报':"
            f"fontsize=22:fontcolor=white:"
            f"x=35:y={HEIGHT-105}:"
            f"enable='gte(t,0.2)'[n7]"
        ),
        (
            f"[n7]drawtext={fa}:text='{e_source}':"
            f"fontsize=20:fontcolor=0xcccccc:"
            f"x=240:y={HEIGHT-102}:"
            f"enable='gte(t,0.3)'[n8]"
        ),
        (
            f"[n8]drawtext={fa}:text='@具身智能':"
            f"fontsize=20:fontcolor=0x00e5ff:"
            f"x={WIDTH}-text_w-20:y={HEIGHT-60}:"
            f"enable='gte(t,0.3)'[out]"
        ),
    ])

    args = input_args + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]", "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        output,
    ]
    return _run_ff(args, f"card_{index}")


def generate_summary(output: str, items: list[dict],
                     channel: str = "@具身智能", duration: float = 3.0) -> bool:
    """总结片尾：要点回顾 + 关注引导。"""
    fa = _fa()
    escaped_channel = _esc(channel)

    summary_lines = ""
    circle_nums = ["❶", "❷", "❸", "❹", "❺"]
    for i, item in enumerate(items[:5]):
        short = item.get("title", "")[:18]
        num = circle_nums[i] if i < len(circle_nums) else f"#{i+1}"
        summary_lines += f"{num} {_esc(short)}\\n"

    filters = [
        _gradient_bg(duration),
        (
            f"[_grad]drawtext={fa}:text='📌 今日要点回顾':"
            f"fontsize=40:fontcolor=0xffc107:"
            f"x=(w-text_w)/2:y=100:"
            f"enable='gte(t,0.2)'[s1]"
        ),
        (
            f"[s1]drawtext={fa}:text='{summary_lines}':"
            f"fontsize=28:fontcolor=white:"
            f"line_spacing=18:"
            f"x=60:y=220:"
            f"enable='gte(t,0.4)'[s2]"
        ),
        f"color=c=0xffc107:s={WIDTH-100}x3:d={duration}:r={FPS}[_divider]",
        f"[s2][_divider]overlay=50:{HEIGHT-350}[s3]",
        (
            f"[s3]drawtext={fa}:text='关注 {escaped_channel}':"
            f"fontsize=48:fontcolor=0xffc107:"
            f"x=(w-text_w)/2:y={HEIGHT-300}:"
            f"enable='gte(t,0.6)'[s4]"
        ),
        (
            f"[s4]drawtext={fa}:text='每日更新 · 具身智能 · 机器人资讯':"
            f"fontsize=24:fontcolor=0xbb86fc:"
            f"x=(w-text_w)/2:y={HEIGHT-230}:"
            f"enable='gte(t,0.8)'[s5]"
        ),
        (
            f"[s5]drawtext={fa}:text='❤ 点赞   ⭐ 收藏   ↗ 转发':"
            f"fontsize=28:fontcolor=white:"
            f"x=(w-text_w)/2:y={HEIGHT-160}:"
            f"enable='gte(t,1.0)'[out]"
        ),
    ]

    args = [
        "-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01",
        "-filter_complex", ";".join(filters),
        "-map", "[out]", "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        output,
    ]
    return _run_ff(args, "summary")


def compose_with_transitions(
    clips: list[str], output: str,
    transition: str = "fade", trans_duration: float = 0.3,
) -> bool:
    if not clips:
        return False
    if len(clips) == 1:
        shutil.copy(clips[0], output)
        return True

    durations = []
    for c in clips:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", c],
            capture_output=True, text=True,
        )
        durations.append(float(probe.stdout.strip()))

    inputs = []
    for c in clips:
        inputs.extend(["-i", c])

    filter_parts = []
    offsets = []
    cumulative = 0.0
    for i, d in enumerate(durations):
        if i == 0:
            cumulative = d - trans_duration
        else:
            cumulative += d - trans_duration
        offsets.append(cumulative)

    if len(clips) == 2:
        offset = durations[0] - trans_duration
        filter_parts.append(
            f"[0:v][1:v]xfade=transition={transition}:"
            f"duration={trans_duration}:offset={offset}[out]"
        )
    else:
        prev = "[0:v]"
        for i in range(1, len(clips)):
            offset = offsets[i - 1]
            out_label = "[out]" if i == len(clips) - 1 else f"[v{i}]"
            filter_parts.append(
                f"{prev}[{i}:v]xfade=transition={transition}:"
                f"duration={trans_duration}:offset={offset}{out_label}"
            )
            prev = out_label if i < len(clips) - 1 else ""

    args = inputs + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        output,
    ]
    return _run_ff(args, "compose")


def build_news_video(
    items: list[dict],
    output: str,
    image_dir: Optional[str] = None,
    channel: str = "@具身智能",
    hook_duration: float = 2.5,
    card_duration: float = 4.0,
    summary_duration: float = 3.0,
    transition: str = "fade",
    trans_duration: float = 0.3,
) -> bool:
    if not items:
        print("No news items provided", file=sys.stderr)
        return False

    with tempfile.TemporaryDirectory() as workdir:
        wd = Path(workdir)
        clips = []

        hook_title = "今日具身智能\n有哪些大事？"
        print("  生成钩子片头...", flush=True)
        hook_path = str(wd / "hook.mp4")
        if not generate_hook(hook_path, hook_title, channel=channel, duration=hook_duration):
            return False
        clips.append(hook_path)

        for i, item in enumerate(items):
            idx = i + 1
            title = item.get("title", f"新闻 {idx}")
            source = item.get("source", "未知来源")
            img = None
            if image_dir:
                img_file = Path(image_dir) / f"illustration_{idx}.png"
                if img_file.exists():
                    img = str(img_file)
            if not img and item.get("image_path"):
                img = item["image_path"]

            print(f"  生成新闻卡片 {idx}/{len(items)}: {title[:30]}...", flush=True)
            card_path = str(wd / f"card_{idx}.mp4")
            if not generate_news_card(
                card_path, idx, title, source,
                image_path=img, duration=card_duration,
            ):
                return False
            clips.append(card_path)

        print("  生成总结片尾...", flush=True)
        summary_path = str(wd / "summary.mp4")
        if not generate_summary(summary_path, items, channel=channel, duration=summary_duration):
            return False
        clips.append(summary_path)

        print(f"  合成视频 ({len(clips)} 段, {transition} 转场)...", flush=True)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        if not compose_with_transitions(clips, output, transition=transition,
                                        trans_duration=trans_duration):
            return False

    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: video_template.py <items.json> [--output out.mp4] [--image-dir dir]",
              file=sys.stderr)
        sys.exit(1)

    items_path = sys.argv[1]
    output = "outputs/drafts/news_video.mp4"
    image_dir = None

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]
    if "--image-dir" in sys.argv:
        idx = sys.argv.index("--image-dir")
        if idx + 1 < len(sys.argv):
            image_dir = sys.argv[idx + 1]

    with open(items_path, encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("items", [])

    if not items:
        print("No items found", file=sys.stderr)
        sys.exit(1)

    success = build_news_video(items[:5], output, image_dir=image_dir)
    if success:
        print(f"Output: {output}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
