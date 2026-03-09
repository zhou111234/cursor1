#!/usr/bin/env python3
"""
演讲稿 + TTS 配音引擎。
为每条新闻生成专业解说词，再用 DashScope CosyVoice 合成语音。
"""

import json
import os
import re
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def write_narration(item: dict, index: int, total: int, api_key: str) -> str:
    """为单条新闻生成演讲稿。"""
    title = item.get("title", "")
    summary = item.get("summary", "")
    source = item.get("source", "")
    method = item.get("method_summary", "")
    abstract = item.get("paper_abstract", "")
    is_paper = "论文" in title or "HF论文" in title or bool(item.get("paper_url"))

    if is_paper and (method or abstract):
        prompt = (
            f"你是科技短视频主播。请为以下AI论文写一段30-50字的解说词，"
            f"用通俗的语言解释核心方法和创新点，适合短视频口播，语气自信、简洁。\n"
            f"标题：{title}\n"
            f"方法概要：{method or abstract[:200]}"
        )
    elif "GitHub" in source:
        prompt = (
            f"你是科技短视频主播。请为以下开源项目写一段20-35字的解说词，"
            f"突出项目用途和亮点，适合短视频口播。\n"
            f"标题：{title}\n摘要：{summary[:150]}"
        )
    else:
        prompt = (
            f"你是科技短视频主播，正在录制一期具身智能快报。"
            f"这是第{index}条，共{total}条新闻。\n"
            f"请为以下新闻写一段25-45字的解说词。要求：\n"
            f"- 语气自信、节奏明快，像新闻主播\n"
            f"- 开头不要'大家好'，直接切入内容\n"
            f"- 必须包含具体的公司名或产品名\n"
            f"- 结尾不要'敬请期待'之类的套话\n\n"
            f"标题：{title}\n摘要：{summary[:200]}\n来源：{source}"
        )

    try:
        from dashscope import Generation
        rsp = Generation.call(
            model="qwen-turbo", api_key=api_key,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
        )
        if rsp.status_code == 200:
            text = rsp.output.choices[0].message.content.strip()
            text = re.sub(r"[""「」【】]", "", text)
            text = text.strip('"\'')
            return text
    except Exception as e:
        print(f"  演讲稿生成失败: {e}", file=sys.stderr)

    if method:
        return method
    return f"{title}。{summary[:60]}" if summary and summary != title else title


def synthesize_tts(text: str, output_path: str) -> bool:
    """TTS 语音合成。"""
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        return False
    try:
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        synth = SpeechSynthesizer(model="cosyvoice-v1", voice="longxiaochun")
        audio = synth.call(text=text)
        if audio and len(audio) > 1000:
            with open(output_path, "wb") as f:
                f.write(audio)
            return True
    except Exception as e:
        print(f"  TTS 合成失败: {e}", file=sys.stderr)
    return False


def process_items(items: list[dict], output_dir: str) -> list[dict]:
    """为所有条目生成演讲稿 + TTS 音频。返回增强后的条目列表。"""
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    enhanced = []
    for i, item in enumerate(items):
        idx = i + 1
        title = item.get("title", "")[:35]
        print(f"  [{idx}/{len(items)}] {title}...")

        narration = write_narration(item, idx, len(items), api_key) if api_key else item.get("title", "")
        print(f"    稿: {narration[:50]}...")

        audio_path = str(out / f"narration_{idx}.mp3")
        tts_ok = synthesize_tts(narration, audio_path) if api_key else False
        if not tts_ok:
            audio_path = ""

        enhanced.append({
            **item,
            "narration": narration,
            "narration_audio": audio_path,
        })

    return enhanced


def main():
    if len(sys.argv) < 2:
        print("Usage: narration_engine.py <items.json> [--output-dir dir]", file=sys.stderr)
        sys.exit(1)

    items_path = sys.argv[1]
    output_dir = "outputs/drafts/narrations"
    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = sys.argv[idx + 1]

    with open(items_path, encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("items", [])

    enhanced = process_items(items, output_dir)

    out_file = Path(output_dir) / "enhanced_items.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(enhanced, f, ensure_ascii=False, indent=2)
    print(f"Output: {out_file} ({len(enhanced)} items)")


if __name__ == "__main__":
    main()
