#!/usr/bin/env python3
"""
视频模板引擎 v5 — 纯净版
画面：全屏实拍视频切片 + 底部字幕，无其余装饰元素。
音频：AI 配音同步。
素材来源：Bilibili 搜索（yt-dlp）。
"""

import json
import os
import re
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
YT_DLP = shutil.which("yt-dlp") or str(Path.home() / ".local/bin/yt-dlp")


def _ff(args: list[str], label: str = "") -> bool:
    cmd = ["ffmpeg", "-y"] + args
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  FFmpeg error ({label}): {e.stderr.decode()[-400:]}", file=sys.stderr)
        return False


def _fa() -> str:
    return f"fontfile={FONT}" if Path(FONT).exists() else "font=WenQuanYi Micro Hei"


def _esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace('"', '\\"')


def _wrap(t: str, n: int = 18) -> str:
    lines = []
    while len(t) > n:
        lines.append(t[:n])
        t = t[n:]
    if t:
        lines.append(t)
    return "\n".join(lines)


# ── 素材搜索 ──────────────────────────────────────────

COMPANY_SEARCH_MAP = {
    "Figure AI": "Figure AI 机器人 发布会", "Helix": "Figure AI Helix 演示",
    "NVIDIA": "NVIDIA 机器人 发布", "nvidia": "NVIDIA 发布会 AI",
    "Unitree": "宇树科技 发布 机器人", "宇树": "宇树科技 发布会",
    "unifolm": "宇树科技 采访",
    "Agibot": "智元机器人 发布", "智元": "智元机器人 采访",
    "agibot": "智元机器人 发布会",
    "智平方": "智平方 采访 机器人", "AIGS": "智平方 AIGS 发布",
    "Galbot": "银河通用 机器人 采访", "银河通用": "银河通用 发布会",
    "Robot Era": "星动纪元 机器人 发布", "星动纪元": "星动纪元 采访",
    "Tesla": "特斯拉 Optimus 发布会", "Optimus": "特斯拉 Optimus 演示",
    "elonmusk": "马斯克 机器人 采访", "Musk": "马斯克 Optimus 发布",
    "Dexmal": "德速科技 机器人 演示", "1X": "1X Technologies 机器人 演示",
    "Boston Dynamics": "波士顿动力 Atlas 发布", "Qwen": "通义千问 发布会 模型",
    "Spirit": "Spirit AI 机器人 演示",
}

MODEL_SEARCH_SUFFIX = ["发布会", "模型 介绍", "演示 测评"]


def search_video_clip(title: str, source: str, output_path: str,
                      max_duration: int = 12) -> bool:
    """从 Bilibili 搜索采访/发布会/演示视频切片。"""
    env = os.environ.copy()
    env["PATH"] = str(Path.home() / ".deno/bin") + ":" + str(Path.home() / ".local/bin") + ":" + env.get("PATH", "")

    queries = []
    combined = title + " " + source

    # 1) 公司名映射（已含"采访""发布会"等关键词）
    for key, search_term in COMPANY_SEARCH_MAP.items():
        if key.lower() in combined.lower():
            queries.append(search_term)
            break

    # 2) 模型类新闻：追加模型名+发布会/测评搜索
    is_model = any(kw in combined.lower() for kw in
                   ["模型", "model", "huggingface", "hf论文", "sota"])
    if is_model:
        model_name = re.search(r"[\w/-]+/[\w.-]+", title)
        if model_name:
            short = model_name.group().split("/")[-1]
            for suffix in MODEL_SEARCH_SUFFIX:
                queries.append(f"{short} {suffix}")

    # 3) 通用关键词 + "采访/演讲"后缀
    clean = re.sub(r"\[.*?\]|【.*?】|（.*?）|\(.*?\)", " ", title)
    clean = re.sub(r"[|｜：:,，。.!！?？\"'⭐]", " ", clean)
    clean = re.sub(r"\d{4}[年./-]\d{1,2}[月./-]?\d{0,2}[日]?", "", clean)
    clean = re.sub(r"(模型更新|Document|Center|ICP|备案)", "", clean)
    words = [w for w in re.sub(r"\s+", " ", clean).strip().split() if len(w) >= 2][:3]
    if words:
        queries.append(" ".join(words) + " 采访")
        queries.append(" ".join(words) + " 发布")

    if not queries:
        queries.append("具身智能 机器人 采访")

    for q in queries[:4]:
        try:
            subprocess.run(
                [YT_DLP, "--download-sections", f"*0-{max_duration}",
                 "--max-downloads", "1", "--no-playlist",
                 "-o", output_path, f"bilisearch1:{q}"],
                capture_output=True, text=True, timeout=25, env=env,
            )
            if Path(output_path).exists() and Path(output_path).stat().st_size > 10000:
                return True
        except Exception:
            pass
    return False


# ── 片段生成 ──────────────────────────────────────────

def generate_segment(
    output: str, index: int, title: str, source: str,
    video_clip: Optional[str] = None,
    audio_path: Optional[str] = None,
    duration: float = 8.0,
) -> bool:
    """生成单条新闻片段：全屏实拍/纯色 + 底部字幕 + 配音。"""
    fa = _fa()

    has_audio = audio_path and Path(audio_path).exists()
    if has_audio:
        aprobe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True)
        try:
            duration = max(duration, float(aprobe.stdout.strip()) + 0.5)
        except (ValueError, AttributeError):
            has_audio = False

    has_clip = video_clip and Path(video_clip).exists()
    e_title = _esc(_wrap(title, n=18))
    e_src = _esc(source[:35])

    if has_clip:
        input_args = ["-i", video_clip]
        vf = (
            f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT}[_bg];"
            f"[_bg]drawbox=x=0:y={HEIGHT-260}:w={WIDTH}:h=260:"
            f"color=0x000000@0.55:t=fill[_d1];"
            f"[_d1]drawtext={fa}:text='{e_title}':"
            f"fontsize=36:fontcolor=white:line_spacing=10:"
            f"x=30:y={HEIGHT-245}:enable='gte(t,0.2)'[_d2];"
            f"[_d2]drawtext={fa}:text='{e_src}':"
            f"fontsize=18:fontcolor=0xbbbbbb:"
            f"x=30:y={HEIGHT-55}:enable='gte(t,0.4)'[out]"
        )
    else:
        input_args = ["-f", "lavfi", "-i", "nullsrc=s=1x1:d=0.01"]
        vf = (
            f"color=c=0x0a0a14:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}[_bg];"
            f"[_bg]drawtext={fa}:text='{e_title}':"
            f"fontsize=40:fontcolor=white:line_spacing=12:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-30[_d1];"
            f"[_d1]drawtext={fa}:text='{e_src}':"
            f"fontsize=20:fontcolor=0xaaaaaa:"
            f"x=(w-text_w)/2:y=(h)/2+100[out]"
        )

    if has_audio:
        input_args.extend(["-i", audio_path])
        aidx = len([a for a in input_args if a == "-i"]) - 1
        return _ff(input_args + [
            "-filter_complex", vf,
            "-map", "[out]", "-map", f"{aidx}:a",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(duration), "-shortest",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), output,
        ], f"seg_{index}")
    else:
        return _ff(input_args + [
            "-filter_complex", vf,
            "-map", "[out]", "-t", str(duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), output,
        ], f"seg_{index}")


# ── 合并 ──────────────────────────────────────────────

def compose_clips(clips: list[str], output: str) -> bool:
    """合并片段，保留音频。无音频片段补静音。"""
    if not clips:
        return False
    if len(clips) == 1:
        shutil.copy(clips[0], output)
        return True

    with tempfile.TemporaryDirectory() as td:
        normalized = []
        for i, c in enumerate(clips):
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "stream=codec_type",
                 "-of", "csv=p=0", c], capture_output=True, text=True)
            has_audio = "audio" in probe.stdout
            norm = os.path.join(td, f"n_{i}.mp4")
            if has_audio:
                ok = _ff(["-i", c, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "1",
                          "-r", str(FPS), norm], f"norm_{i}")
            else:
                dur_p = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", c],
                    capture_output=True, text=True)
                dur = dur_p.stdout.strip() or "5"
                ok = _ff(["-i", c, "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={dur}",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "128k", "-r", str(FPS),
                          "-shortest", norm], f"norm_s_{i}")
            if not ok:
                return False
            normalized.append(norm)

        concat_file = os.path.join(td, "list.txt")
        with open(concat_file, "w") as f:
            for p in normalized:
                f.write(f"file '{p}'\n")
        return _ff(["-f", "concat", "-safe", "0", "-i", concat_file,
                     "-c", "copy", output], "concat")


# ── 主流程 ──────────────────────────────────────────────

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

        for i, item in enumerate(items):
            idx = i + 1
            title = item.get("title", f"新闻 {idx}")
            source = item.get("source", "")
            audio = item.get("narration_audio", "")
            if audio and not Path(audio).exists():
                audio = None

            # 搜索视频切片
            clip_path = str(wd / f"clip_{idx}.mp4")
            print(f"  [{idx}/{len(items)}] 搜索视频: {title[:30]}...", flush=True)
            found = search_video_clip(title, source, clip_path)
            print(f"    {'✓ 找到' if found else '✗ 未找到，使用纯色背景'}", flush=True)

            img = None
            if not found and image_dir:
                img_file = Path(image_dir) / f"illustration_{idx}.png"
                if img_file.exists():
                    img = str(img_file)
                    clip_path = None

            seg = str(wd / f"seg_{idx}.mp4")
            if not generate_segment(seg, idx, title, source,
                                    video_clip=clip_path if found else None,
                                    audio_path=audio):
                continue
            clips.append(seg)

        if not clips:
            return False

        print(f"  合并 {len(clips)} 段...", flush=True)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        return compose_clips(clips, output)


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
        sys.exit(1)

    success = build_news_video(items[:5], output, image_dir=image_dir)
    if success:
        print(f"Output: {output}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
