#!/usr/bin/env python3
"""
NEXUS 情报终端 — 视频模板引擎 v4
风格：赛博朋克 HUD + 极简数据面板 + 扫描线 + 打字机效果
结构：系统启动(2s) → 情报卡片×N(每条6s) → 终端关闭(2s)
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

# 颜色体系
C_BG = "0x06080f"        # 深空黑
C_CYAN = "0x00e5ff"      # HUD 青色
C_ORANGE = "0xff6d00"    # 警报橙
C_DIM = "0x1a2a3a"       # 暗灰蓝
C_TEXT = "0xe0e8f0"      # 亮白灰
C_MUTED = "0x607080"     # 暗文字


def _ff(args: list[str], label: str = "") -> bool:
    cmd = ["ffmpeg", "-y"] + args
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  FFmpeg error ({label}): {e.stderr.decode()[-600:]}", file=sys.stderr)
        return False


def _fa() -> str:
    return f"fontfile={FONT}" if Path(FONT).exists() else "font=WenQuanYi Micro Hei"


def _esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace('"', '\\"')


def _wrap(t: str, n: int = 16) -> str:
    lines = []
    while len(t) > n:
        lines.append(t[:n])
        t = t[n:]
    if t:
        lines.append(t)
    return "\n".join(lines)


def _hud_base(dur: float) -> str:
    """深空背景 + 顶部状态栏 + 底部数据条。"""
    fa = _fa()
    date_str = _esc(datetime.now().strftime("%Y.%m.%d"))
    return (
        f"color=c={C_BG}:s={WIDTH}x{HEIGHT}:d={dur}:r={FPS}[_bg0];"
        f"color=c={C_DIM}:s={WIDTH}x52:d={dur}:r={FPS}[_topbar];"
        f"[_bg0][_topbar]overlay=0:0[_b1];"
        f"color=c={C_CYAN}:s={WIDTH}x2:d={dur}:r={FPS}[_topline];"
        f"[_b1][_topline]overlay=0:52[_b2];"
        f"color=c={C_DIM}:s={WIDTH}x44:d={dur}:r={FPS}[_botbar];"
        f"[_b2][_botbar]overlay=0:{HEIGHT - 44}[_b3];"
        f"color=c={C_CYAN}:s={WIDTH}x2:d={dur}:r={FPS}[_botline];"
        f"[_b3][_botline]overlay=0:{HEIGHT - 44}[_b4];"
        f"[_b4]drawtext={fa}:text='NEXUS':fontsize=20:fontcolor={C_CYAN}:x=16:y=16[_b5];"
        f"[_b5]drawtext={fa}:text='{date_str}':fontsize=16:fontcolor={C_MUTED}:x={WIDTH}-text_w-16:y=20[_b6];"
        f"[_b6]drawtext={fa}:text='SIGNAL ACTIVE':fontsize=14:fontcolor={C_CYAN}:"
        f"x=16:y={HEIGHT - 34}[_base]"
    )


def generate_boot(output: str, duration: float = 2.5) -> bool:
    """系统启动画面。"""
    fa = _fa()
    filters = [
        _hud_base(duration),
        # 中央大 LOGO
        (
            f"[_base]drawtext={fa}:text='N E X U S':"
            f"fontsize=64:fontcolor={C_CYAN}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-100:"
            f"enable='gte(t,0.3)'[t1]"
        ),
        (
            f"[t1]drawtext={fa}:text='EMBODIED AI INTELLIGENCE':"
            f"fontsize=20:fontcolor={C_MUTED}:"
            f"x=(w-text_w)/2:y=(h)/2-20:"
            f"enable='gte(t,0.6)'[t2]"
        ),
        (
            f"[t2]drawtext={fa}:text='SYSTEM ONLINE':"
            f"fontsize=22:fontcolor={C_ORANGE}:"
            f"x=(w-text_w)/2:y=(h)/2+60:"
            f"enable='gte(t,1.2)'[t3]"
        ),
        (
            f"[t3]drawtext={fa}:text='正在加载今日情报...':"
            f"fontsize=18:fontcolor={C_TEXT}@0.5:"
            f"x=(w-text_w)/2:y=(h)/2+120:"
            f"enable='gte(t,1.8)'[out]"
        ),
    ]
    return _ff([
        "-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01",
        "-filter_complex", ";".join(filters),
        "-map", "[out]", "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), output,
    ], "boot")


def generate_intel_card(
    output: str, index: int, title: str, source: str,
    image_path: Optional[str] = None, duration: float = 6.0,
) -> bool:
    """情报卡片：HUD 数据面板 + 配图/实拍 + 标题 + 来源。"""
    fa = _fa()
    wrapped = _wrap(title, n=16)
    e_title = _esc(wrapped)
    e_src = _esc(source[:30])
    idx_str = f"INTEL-{index:03d}"
    e_idx = _esc(idx_str)

    panel_y = 56
    panel_h = HEIGHT - 56 - 48
    img_area_h = 400
    text_y = panel_y + img_area_h + 30

    if image_path and Path(image_path).exists():
        input_args = ["-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01", "-i", image_path]
        img_filters = [
            _hud_base(duration),
            # 左侧青色竖线
            f"color=c={C_CYAN}:s=3x{panel_h}:d={duration}:r={FPS}[_vline]",
            f"[_base][_vline]overlay=24:{panel_y}[_p1]",
            # 图片区域
            (
                f"[1:v]scale=660:{img_area_h}:force_original_aspect_ratio=decrease,"
                f"pad=660:{img_area_h}:(ow-iw)/2:(oh-ih)/2:color={C_BG}[_img]"
            ),
            f"color=c={C_CYAN}:s=664x{img_area_h + 4}:d={duration}:r={FPS}[_imgborder]",
            f"[_p1][_imgborder]overlay=28:{panel_y+6}[_p2]",
            f"[_p2][_img]overlay=30:{panel_y+8}[_p3]",
        ]
    else:
        input_args = ["-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01"]
        text_y = panel_y + 80
        img_filters = [
            _hud_base(duration),
            f"color=c={C_CYAN}:s=3x{panel_h}:d={duration}:r={FPS}[_vline]",
            f"[_base][_vline]overlay=24:{panel_y}[_p3]",
        ]

    text_filters = [
        # 索引编号
        (
            f"[_p3]drawtext={fa}:text='{e_idx}':"
            f"fontsize=18:fontcolor={C_ORANGE}:"
            f"x=40:y={panel_y+10}:"
            f"enable='gte(t,0.15)'[_t1]"
        ),
        # 主标题
        (
            f"[_t1]drawtext={fa}:text='{e_title}':"
            f"fontsize=38:fontcolor={C_TEXT}:"
            f"line_spacing=10:"
            f"x=40:y={text_y}:"
            f"enable='gte(t,0.4)'[_t2]"
        ),
        # 分隔线
        f"color=c={C_CYAN}:s=200x2:d={duration}:r={FPS}[_sep]",
        f"[_t2][_sep]overlay=40:{text_y + 200}[_t3]",
        # 来源标签
        (
            f"[_t3]drawtext={fa}:text='SOURCE':"
            f"fontsize=14:fontcolor={C_CYAN}:"
            f"x=40:y={text_y+220}:"
            f"enable='gte(t,0.6)'[_t4]"
        ),
        (
            f"[_t4]drawtext={fa}:text='{e_src}':"
            f"fontsize=18:fontcolor={C_MUTED}:"
            f"x=150:y={text_y+218}:"
            f"enable='gte(t,0.6)'[_t5]"
        ),
        # 底部品牌
        (
            f"[_t5]drawtext={fa}:text='@具身智能 NEXUS':"
            f"fontsize=14:fontcolor={C_CYAN}@0.5:"
            f"x={WIDTH}-text_w-16:y={HEIGHT-34}:"
            f"enable='gte(t,0.3)'[out]"
        ),
    ]

    all_filters = img_filters + text_filters
    return _ff(input_args + [
        "-filter_complex", ";".join(all_filters),
        "-map", "[out]", "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), output,
    ], f"intel_{index}")


def generate_shutdown(output: str, items: list[dict], duration: float = 3.0) -> bool:
    """终端关闭 / 总结画面。"""
    fa = _fa()

    summary_lines = ""
    for i, item in enumerate(items[:5]):
        short = _esc(item.get("title", "")[:20])
        summary_lines += f"▸ {short}\\n"

    filters = [
        _hud_base(duration),
        (
            f"[_base]drawtext={fa}:text='TODAY BRIEFING':"
            f"fontsize=28:fontcolor={C_ORANGE}:"
            f"x=(w-text_w)/2:y=100:"
            f"enable='gte(t,0.2)'[s1]"
        ),
        (
            f"[s1]drawtext={fa}:text='{summary_lines}':"
            f"fontsize=22:fontcolor={C_TEXT}:"
            f"line_spacing=16:"
            f"x=60:y=200:"
            f"enable='gte(t,0.4)'[s2]"
        ),
        f"color=c={C_CYAN}:s={WIDTH - 100}x2:d={duration}:r={FPS}[_div]",
        f"[s2][_div]overlay=50:{HEIGHT-380}[s3]",
        (
            f"[s3]drawtext={fa}:text='关注 @具身智能':"
            f"fontsize=36:fontcolor={C_CYAN}:"
            f"x=(w-text_w)/2:y={HEIGHT-340}:"
            f"enable='gte(t,0.8)'[s4]"
        ),
        (
            f"[s4]drawtext={fa}:text='NEXUS 每日情报 关注 点赞 转发':"
            f"fontsize=18:fontcolor={C_MUTED}:"
            f"x=(w-text_w)/2:y={HEIGHT-280}:"
            f"enable='gte(t,1.2)'[s5]"
        ),
        (
            f"[s5]drawtext={fa}:text='SESSION ENDED':"
            f"fontsize=20:fontcolor={C_ORANGE}@0.6:"
            f"x=(w-text_w)/2:y={HEIGHT-200}:"
            f"enable='gte(t,2.0)'[out]"
        ),
    ]
    return _ff([
        "-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01",
        "-filter_complex", ";".join(filters),
        "-map", "[out]", "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), output,
    ], "shutdown")


def compose_with_transitions(
    clips: list[str], output: str,
    transition: str = "fadeblack", trans_duration: float = 0.4,
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
            capture_output=True, text=True)
        durations.append(float(probe.stdout.strip()))

    inputs = []
    for c in clips:
        inputs.extend(["-i", c])

    filter_parts = []
    offsets = []
    cum = 0.0
    for i, d in enumerate(durations):
        cum = (d - trans_duration) if i == 0 else cum + d - trans_duration
        offsets.append(cum)

    if len(clips) == 2:
        filter_parts.append(
            f"[0:v][1:v]xfade=transition={transition}:"
            f"duration={trans_duration}:offset={offsets[0]}[out]"
        )
    else:
        prev = "[0:v]"
        for i in range(1, len(clips)):
            out_label = "[out]" if i == len(clips) - 1 else f"[v{i}]"
            filter_parts.append(
                f"{prev}[{i}:v]xfade=transition={transition}:"
                f"duration={trans_duration}:offset={offsets[i-1]}{out_label}"
            )
            prev = out_label if i < len(clips) - 1 else ""

    return _ff(inputs + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), output,
    ], "compose")


def build_news_video(
    items: list[dict], output: str,
    image_dir: Optional[str] = None,
    channel: str = "@具身智能",
) -> bool:
    if not items:
        return False

    with tempfile.TemporaryDirectory() as wd:
        wd = Path(wd)
        clips = []

        print("  生成系统启动...", flush=True)
        boot = str(wd / "boot.mp4")
        if not generate_boot(boot):
            return False
        clips.append(boot)

        for i, item in enumerate(items):
            idx = i + 1
            title = item.get("title", f"情报 {idx}")
            source = item.get("source", "UNKNOWN")
            img = None
            if image_dir:
                img_file = Path(image_dir) / f"illustration_{idx}.png"
                if img_file.exists():
                    img = str(img_file)

            print(f"  生成情报卡片 {idx}/{len(items)}: {title[:30]}...", flush=True)
            card = str(wd / f"card_{idx}.mp4")
            if not generate_intel_card(card, idx, title, source, image_path=img):
                return False
            clips.append(card)

        print("  生成终端关闭...", flush=True)
        shutdown = str(wd / "shutdown.mp4")
        if not generate_shutdown(shutdown, items):
            return False
        clips.append(shutdown)

        print(f"  合成视频 ({len(clips)} 段)...", flush=True)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        if not compose_with_transitions(clips, output):
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
