#!/usr/bin/env python3
"""
实拍素材+配音 视频生产流水线。
流程：每条新闻 → 搜索实拍视频 → 生成配音 → 合成单条 → 合并为完整合辑。
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

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

WIDTH, HEIGHT = 720, 1280
FPS = 25
FONT = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
YT_DLP = shutil.which("yt-dlp") or str(Path.home() / ".local/bin/yt-dlp")
DENO = str(Path.home() / ".deno/bin/deno")


def _run_ff(args: list[str], label: str = "") -> bool:
    cmd = ["ffmpeg", "-y"] + args
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  FFmpeg error ({label}): {e.stderr.decode()[:300]}", file=sys.stderr)
        return False


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace('"', '\\"')


def _fa() -> str:
    return f"fontfile={FONT}" if Path(FONT).exists() else "font=WenQuanYi Micro Hei"


# ── 1. 搜索并下载实拍视频素材 ──────────────────────────────────

def search_and_download_clip(query: str, output_path: str, max_duration: int = 15) -> bool:
    """从 Bilibili 搜索并下载一段与新闻相关的短视频片段。"""
    env = os.environ.copy()
    env["PATH"] = str(Path.home() / ".deno/bin") + ":" + str(Path.home() / ".local/bin") + ":" + env.get("PATH", "")

    clean = re.sub(r"[|｜\[\]【】（）()：:,，。.!！?？\"'""'']", " ", query)
    clean = re.sub(r"\s+", " ", clean).strip()
    keywords = [w for w in clean.split() if len(w) >= 2][:4]
    search_query = " ".join(keywords) if keywords else clean[:20]

    sources = [
        f"bilisearch1:{search_query}",
        f"bilisearch1:{' '.join(keywords[:2])} 机器人" if len(keywords) >= 2 else f"bilisearch1:{search_query} 机器人",
        f"bilisearch1:{keywords[0]} 具身智能" if keywords else f"bilisearch1:具身智能 机器人",
    ]
    for source_tpl in sources:
        try:
            r = subprocess.run(
                [YT_DLP, "--download-sections", f"*0-{max_duration}",
                 "--max-downloads", "1", "--no-playlist",
                 "-o", output_path, source_tpl],
                capture_output=True, text=True, timeout=30, env=env,
            )
            if Path(output_path).exists() and Path(output_path).stat().st_size > 10000:
                return True
        except Exception as e:
            print(f"  下载失败 ({source_tpl[:30]}): {e}", file=sys.stderr)

    return False


def generate_fallback_clip(output_path: str, title: str, duration: float = 8.0) -> bool:
    """无法下载实拍素材时，生成带文字的动态背景作为替代。"""
    fa = _fa()
    e_title = _esc(title[:40])
    filters = (
        f"color=c=0x0a1628:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS},"
        f"drawtext={fa}:text='{e_title}':"
        f"fontsize=44:fontcolor=white:line_spacing=10:"
        f"x=(w-text_w)/2:y=(h-text_h)/2"
    )
    return _run_ff(["-f", "lavfi", "-i", f"nullsrc=s=1x1:d=0.01",
                    "-filter_complex", filters, "-t", str(duration),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    output_path], "fallback_clip")


# ── 2. TTS 配音 ─────────────────────────────────────────────

def generate_tts(text: str, output_path: str) -> bool:
    """使用 DashScope CosyVoice 合成配音。"""
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("  TTS skipped: no DASHSCOPE_API_KEY", file=sys.stderr)
        return False
    try:
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        synth = SpeechSynthesizer(model="cosyvoice-v1", voice="longxiaochun")
        audio = synth.call(text=text)
        if audio and len(audio) > 1000:
            with open(output_path, "wb") as f:
                f.write(audio)
            return True
        print("  TTS returned empty audio", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  TTS error: {e}", file=sys.stderr)
        return False


def generate_narration_text(item: dict) -> str:
    """生成配音文稿。论文类条目优先使用提炼的方法解说，否则改写新闻标题。"""
    title = item.get("title", "")
    summary = item.get("summary", "")
    method = item.get("method_summary", "")

    if method:
        return method

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        return f"{title}。{summary}" if summary != title else title

    is_paper = "论文" in title or "HF论文" in title or item.get("paper_url")
    if is_paper and item.get("paper_abstract"):
        prompt = (
            f"你是AI论文视频解说员。将以下论文内容改写为30-50字的短视频配音文案，"
            f"用中文通俗地解释核心方法和创新点：\n"
            f"标题：{title}\n摘要：{item['paper_abstract'][:300]}"
        )
    else:
        prompt = (
            f"你是短视频配音文案写手。将以下新闻改写为15-25字的口播文案，"
            f"语气自然、通俗易懂、适合短视频配音，不要加标点以外的符号：\n"
            f"标题：{title}\n摘要：{summary[:100]}"
        )

    try:
        from dashscope import Generation
        rsp = Generation.call(
            model="qwen-turbo", api_key=api_key,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
        )
        if rsp.status_code == 200:
            return rsp.output.choices[0].message.content.strip()
    except Exception:
        pass
    return method or (f"{title}。{summary[:60]}" if summary and summary != title else title)


# ── 3. 合成单条新闻视频（实拍 + 字幕 + 配音） ──────────────────

def compose_single_news(
    video_path: str, audio_path: Optional[str],
    title: str, source: str, index: int,
    output_path: str,
) -> bool:
    """将实拍视频 + 配音 + 字幕/标题叠加合成为一条新闻片段。"""
    fa = _fa()
    e_title = _esc(title[:40] if len(title) > 40 else title)
    e_source = _esc(source[:30])
    circle = ["❶", "❷", "❸", "❹", "❺"][index - 1] if index <= 5 else f"#{index}"
    e_num = _esc(circle)

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True)
    vid_dur = float(probe.stdout.strip()) if probe.stdout.strip() else 8.0

    if audio_path and Path(audio_path).exists():
        aprobe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True)
        aud_dur = float(aprobe.stdout.strip()) if aprobe.stdout.strip() else vid_dur
        target_dur = max(vid_dur, aud_dur)
    else:
        target_dur = vid_dur
        audio_path = None

    target_dur = min(target_dur, 15.0)

    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0x0a0a1a,"
        f"drawbox=x=0:y=0:w={WIDTH}:h=100:color=0x000000@0.6:t=fill,"
        f"drawtext={fa}:text='{e_num}':fontsize=48:fontcolor=0xffc107:x=20:y=25,"
        f"drawtext={fa}:text='具身智能快报':fontsize=22:fontcolor=0x00bfff:x=90:y=38,"
        f"drawbox=x=0:y={HEIGHT-120}:w={WIDTH}:h=120:color=0x000000@0.65:t=fill,"
        f"drawtext={fa}:text='{e_title}':fontsize=36:fontcolor=white:line_spacing=8:"
        f"x=(w-text_w)/2:y={HEIGHT-110},"
        f"drawtext={fa}:text='{e_source}  |  @具身智能':fontsize=20:fontcolor=0xaaaaaa:"
        f"x=(w-text_w)/2:y={HEIGHT-30}"
    )

    inputs = ["-i", video_path]
    if audio_path:
        inputs.extend(["-i", audio_path])

    args = inputs + [
        "-filter_complex",
        f"[0:v]{vf}[vout]",
        "-map", "[vout]",
    ]

    if audio_path:
        args.extend(["-map", "1:a", "-c:a", "aac", "-b:a", "128k"])
    else:
        args.extend(["-an"])

    args.extend([
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-t", str(target_dur),
        "-shortest",
        output_path,
    ])
    return _run_ff(args, f"compose_news_{index}")


# ── 4. 合并多条为完整合辑 ────────────────────────────────────

def concat_clips(clips: list[str], output: str) -> bool:
    """用 concat filter 合并多个片段（可能有不同编码）。"""
    if not clips:
        return False
    if len(clips) == 1:
        shutil.copy(clips[0], output)
        return True

    inputs = []
    filter_parts = []
    for i, c in enumerate(clips):
        inputs.extend(["-i", c])
        filter_parts.append(f"[{i}:v]scale={WIDTH}:{HEIGHT},setsar=1[v{i}]")

    v_concat = "".join(f"[v{i}]" for i in range(len(clips)))
    a_parts = []
    for i, c in enumerate(clips):
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", c], capture_output=True, text=True)
        has_audio = "audio" in probe.stdout
        if has_audio:
            a_parts.append(f"[{i}:a]")
        else:
            filter_parts.append(
                f"aevalsrc=0:d=1:s=44100:c=mono[silence{i}]"
            )
            a_parts.append(f"[silence{i}]")

    a_concat = "".join(a_parts)
    filter_parts.append(f"{v_concat}concat=n={len(clips)}:v=1:a=0[vout]")
    filter_parts.append(f"{a_concat}concat=n={len(clips)}:v=0:a=1[aout]")

    args = inputs + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k",
        output,
    ]
    return _run_ff(args, "concat_all")


# ── 5. 主流程 ────────────────────────────────────────────────

def build_realvideo(items: list[dict], output: str, workdir: str) -> bool:
    """完整流水线：每条新闻 → 下载实拍 → 配音 → 合成 → 合并。"""
    wd = Path(workdir)
    clips = []

    for i, item in enumerate(items):
        idx = i + 1
        title = item.get("title", f"新闻{idx}")
        source = item.get("source", "未知来源")
        summary = item.get("summary", title)

        print(f"\n── 新闻 {idx}/{len(items)}: {title[:35]}... ──")

        # Step A: 搜索并下载实拍素材
        clip_path = str(wd / f"clip_{idx}.mp4")
        print(f"  [A] 搜索实拍素材...")
        if not search_and_download_clip(title, clip_path):
            print(f"  [A] 实拍未找到，生成替代画面")
            generate_fallback_clip(clip_path, title)

        if not Path(clip_path).exists():
            print(f"  跳过: 无法获取素材", file=sys.stderr)
            continue

        # Step B: 生成配音文稿 + TTS
        print(f"  [B] 生成配音...")
        narration = generate_narration_text(item)
        print(f"      文稿: {narration[:50]}...")
        audio_path = str(wd / f"audio_{idx}.mp3")
        if not generate_tts(narration, audio_path):
            audio_path = None
            print(f"  [B] 配音失败，使用静音")

        # Step C: 合成单条视频（实拍 + 字幕 + 配音）
        print(f"  [C] 合成视频...")
        single_path = str(wd / f"news_{idx}.mp4")
        if compose_single_news(clip_path, audio_path, title, source, idx, single_path):
            clips.append(single_path)
            dur_probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", single_path],
                capture_output=True, text=True)
            dur = dur_probe.stdout.strip()
            print(f"  [✓] 完成 ({dur}s)")
        else:
            print(f"  [✗] 合成失败", file=sys.stderr)

    if not clips:
        print("无有效片段", file=sys.stderr)
        return False

    # Step D: 合并所有片段
    print(f"\n── 合并 {len(clips)} 条新闻片段 ──")
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    if concat_clips(clips, output):
        return True
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: realvideo_pipeline.py <items.json> [--output out.mp4]", file=sys.stderr)
        sys.exit(1)

    items_path = sys.argv[1]
    output = "outputs/drafts/realvideo_news.mp4"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]

    with open(items_path, encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("items", [])
    if not items:
        print("No items", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as workdir:
        success = build_realvideo(items[:5], output, workdir)

    if success:
        print(f"\nOutput: {output}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
