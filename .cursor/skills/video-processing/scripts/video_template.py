#!/usr/bin/env python3
"""
视频模板引擎：仿 YouTube 科技资讯短视频风格。
结构：片头(3s) → 多条新闻轮播(每条5s) → 片尾(3s)，段落间有转场。
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


def _font_arg() -> str:
    if Path(FONT).exists():
        return f"fontfile={FONT}"
    return f"font={FONT_FALLBACK}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace('"', '\\"')


def _wrap_text(text: str, max_chars: int = 16) -> str:
    """Break long text into lines for drawtext."""
    lines = []
    while len(text) > max_chars:
        cut = text[:max_chars]
        lines.append(cut)
        text = text[max_chars:]
    if text:
        lines.append(text)
    return "\n".join(lines)


def generate_intro(output: str, channel: str = "@具身智能",
                   topic: str = "今日AI快讯", duration: float = 3.0) -> bool:
    date_str = datetime.now().strftime("%Y.%m.%d")
    fa = _font_arg()
    escaped_channel = _escape(channel)
    escaped_topic = _escape(topic)
    escaped_date = _escape(date_str)

    filters = [
        f"color=c=0x0a1628:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}[bg]",
        f"color=c=0x1a3a5c:s={WIDTH}x{int(HEIGHT*0.35)}:d={duration}:r={FPS}[topbar]",
        "[bg][topbar]overlay=0:0[base]",
        f"color=c=0x00bfff@0.15:s={WIDTH}x4:d={duration}:r={FPS}[line]",
        f"[base][line]overlay=0:{int(HEIGHT*0.35)}[bg2]",
        (
            f"[bg2]drawtext={fa}:text='{escaped_topic}':"
            f"fontsize=64:fontcolor=white:"
            f"x=(w-text_w)/2:y=200:"
            f"enable='gte(t,0.3)'"
            f"[t1]"
        ),
        (
            f"[t1]drawtext={fa}:text='{escaped_date}':"
            f"fontsize=36:fontcolor=0x88ccff:"
            f"x=(w-text_w)/2:y=300:"
            f"enable='gte(t,0.5)'"
            f"[t2]"
        ),
        (
            f"[t2]drawtext={fa}:text='{escaped_channel}':"
            f"fontsize=40:fontcolor=0x00e5ff:"
            f"x=(w-text_w)/2:y={HEIGHT-200}:"
            f"enable='gte(t,0.6)'"
            f"[t3]"
        ),
        (
            f"[t3]drawtext={fa}:text='━━━ 具身智能 · 机器人 · AI ━━━':"
            f"fontsize=24:fontcolor=0x4488aa:"
            f"x=(w-text_w)/2:y={int(HEIGHT*0.35)-50}:"
            f"enable='gte(t,0.4)'"
            f"[out]"
        ),
    ]

    args = [
        "-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01",
        "-filter_complex", ";".join(filters),
        "-map", "[out]",
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        output,
    ]
    return _run_ff(args, "intro")


def generate_news_slide(
    output: str,
    index: int,
    title: str,
    source: str,
    image_path: Optional[str] = None,
    duration: float = 5.0,
) -> bool:
    fa = _font_arg()
    num_str = f"{index:02d}"
    wrapped_title = _wrap_text(title, max_chars=14)
    escaped_title = _escape(wrapped_title)
    escaped_source = _escape(source)
    escaped_num = _escape(num_str)

    if image_path and Path(image_path).exists():
        filter_parts = [
            f"color=c=0x0a1628:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}[bg]",
            f"[1:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT},format=rgba,"
            f"colorchannelmixer=aa=0.35[img]",
            "[bg][img]overlay=0:0[base]",
        ]
        input_args = [
            "-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01",
            "-i", image_path,
        ]
    else:
        grad_color = ["0x0a2a4a", "0x1a0a3a", "0x0a3a2a"][index % 3]
        filter_parts = [
            f"color=c={grad_color}:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}[base]",
        ]
        input_args = ["-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01"]

    filter_parts.extend([
        f"color=c=0x000000@0.6:s={WIDTH}x220:d={duration}:r={FPS}[topband]",
        f"[base][topband]overlay=0:0[b1]",
        f"color=c=0x000000@0.5:s={WIDTH}x160:d={duration}:r={FPS}[botband]",
        f"[b1][botband]overlay=0:{HEIGHT-160}[b2]",
        f"color=c=0x00bfff:s=6x120:d={duration}:r={FPS}[accent]",
        f"[b2][accent]overlay=30:40[b3]",
        (
            f"[b3]drawtext={fa}:text='{escaped_num}':"
            f"fontsize=80:fontcolor=0x00e5ff:"
            f"x=50:y=50:"
            f"enable='gte(t,0.2)'"
            f"[n1]"
        ),
        (
            f"[n1]drawtext={fa}:text='{escaped_title}':"
            f"fontsize=48:fontcolor=white:"
            f"line_spacing=12:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-40:"
            f"enable='gte(t,0.3)'"
            f"[n2]"
        ),
        (
            f"[n2]drawtext={fa}:text='来源\\: {escaped_source}':"
            f"fontsize=28:fontcolor=0x88ccff:"
            f"x=30:y={HEIGHT-130}:"
            f"enable='gte(t,0.4)'"
            f"[n3]"
        ),
        (
            f"[n3]drawtext={fa}:text='@具身智能':"
            f"fontsize=24:fontcolor=white@0.6:"
            f"x={WIDTH}-text_w-30:y={HEIGHT-80}:"
            f"enable='gte(t,0.4)'"
            f"[out]"
        ),
    ])

    args = input_args + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]",
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        output,
    ]
    return _run_ff(args, f"slide_{index}")


def generate_outro(output: str, channel: str = "@具身智能",
                   duration: float = 3.0) -> bool:
    fa = _font_arg()
    escaped_channel = _escape(channel)

    filters = [
        f"color=c=0x0a1628:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}[bg]",
        f"color=c=0x1a3a5c:s={WIDTH}x{int(HEIGHT*0.3)}:d={duration}:r={FPS}[bar]",
        f"[bg][bar]overlay=0:{int(HEIGHT*0.35)}[base]",
        (
            f"[base]drawtext={fa}:text='关注 {escaped_channel}':"
            f"fontsize=56:fontcolor=0x00e5ff:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-60:"
            f"enable='gte(t,0.3)'"
            f"[t1]"
        ),
        (
            f"[t1]drawtext={fa}:text='获取更多 AI · 机器人 资讯':"
            f"fontsize=32:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+40:"
            f"enable='gte(t,0.5)'"
            f"[t2]"
        ),
        (
            f"[t2]drawtext={fa}:text='▶ 点赞 · 关注 · 转发':"
            f"fontsize=28:fontcolor=0x88ccff:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+120:"
            f"enable='gte(t,0.7)'"
            f"[out]"
        ),
    ]

    args = [
        "-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01",
        "-filter_complex", ";".join(filters),
        "-map", "[out]",
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        output,
    ]
    return _run_ff(args, "outro")


def compose_with_transitions(
    clips: list[str],
    output: str,
    transition: str = "fade",
    trans_duration: float = 0.5,
) -> bool:
    if not clips:
        print("No clips to compose", file=sys.stderr)
        return False
    if len(clips) == 1:
        shutil.copy(clips[0], output)
        return True

    durations = []
    for c in clips:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", c],
            capture_output=True, text=True
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
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        output,
    ]
    return _run_ff(args, "compose")


def build_news_video(
    items: list[dict],
    output: str,
    image_dir: Optional[str] = None,
    channel: str = "@具身智能",
    topic: str = "今日AI快讯",
    intro_duration: float = 3.0,
    slide_duration: float = 5.0,
    outro_duration: float = 3.0,
    transition: str = "fade",
    trans_duration: float = 0.5,
) -> bool:
    if not items:
        print("No news items provided", file=sys.stderr)
        return False

    with tempfile.TemporaryDirectory() as workdir:
        wd = Path(workdir)
        clips = []

        print("  生成片头...", flush=True)
        intro_path = str(wd / "intro.mp4")
        if not generate_intro(intro_path, channel=channel, topic=topic, duration=intro_duration):
            print("片头生成失败", file=sys.stderr)
            return False
        clips.append(intro_path)

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

            print(f"  生成新闻片段 {idx}/{len(items)}: {title[:30]}...", flush=True)
            slide_path = str(wd / f"slide_{idx}.mp4")
            if not generate_news_slide(
                slide_path, idx, title, source,
                image_path=img, duration=slide_duration
            ):
                print(f"片段 {idx} 生成失败", file=sys.stderr)
                return False
            clips.append(slide_path)

        print("  生成片尾...", flush=True)
        outro_path = str(wd / "outro.mp4")
        if not generate_outro(outro_path, channel=channel, duration=outro_duration):
            print("片尾生成失败", file=sys.stderr)
            return False
        clips.append(outro_path)

        print(f"  合成视频 ({len(clips)} 段, {transition} 转场)...", flush=True)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        if not compose_with_transitions(clips, output, transition=transition,
                                        trans_duration=trans_duration):
            print("视频合成失败", file=sys.stderr)
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
