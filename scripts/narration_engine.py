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


def _is_model_news(item: dict) -> bool:
    """判断是否是模型相关新闻。"""
    indicators = ["模型更新", "HuggingFace", "模型", "model", "SOTA",
                  "benchmark", "榜单", "开源", "发布"]
    combined = (item.get("title", "") + item.get("source", "")).lower()
    return any(kw.lower() in combined for kw in indicators)


def _research_model(item: dict, api_key: str) -> str:
    """深度研究模型：调用 LLM 联网搜索榜单排名、亮点、与竞品对比。"""
    title = item.get("title", "")
    summary = item.get("summary", "")

    try:
        from dashscope import Generation
        rsp = Generation.call(
            model="qwen-plus", api_key=api_key,
            messages=[{"role": "user", "content":
                f"我需要为以下AI模型制作一条短视频。请帮我深度调研并回答：\n"
                f"模型信息：{title}\n补充：{summary[:200]}\n\n"
                f"请搜索并回答以下问题（用中文）：\n"
                f"1. 这个模型在哪些榜单或基准测试上取得了最好成绩？（如MMLU、HumanEval、Arena等）具体排名和分数是多少？\n"
                f"2. 相比同类竞品模型（如GPT-4、Claude、Llama、DeepSeek等），它的核心亮点和差异化优势是什么？\n"
                f"3. 这个模型最适合的应用场景是什么？\n\n"
                f"请用简洁的中文回答，每个问题2-3句话。如果找不到确切信息，请说明。"}],
            result_format="message",
            enable_search=True,
        )
        if rsp.status_code == 200:
            return rsp.output.choices[0].message.content.strip()
    except Exception as e:
        print(f"    模型调研失败: {e}", file=sys.stderr)
    return ""


def write_narration(item: dict, index: int, total: int, api_key: str) -> str:
    """为单条新闻生成演讲稿。模型类先做深度调研再写稿。"""
    title = item.get("title", "")
    summary = item.get("summary", "")
    source = item.get("source", "")
    method = item.get("method_summary", "")
    abstract = item.get("paper_abstract", "")

    from dashscope import Generation

    is_model = _is_model_news(item)

    if is_model:
        print(f"    [调研] 搜索模型榜单和亮点...", file=sys.stderr)
        research = _research_model(item, api_key)
        if research:
            print(f"    [调研] 获取到 {len(research)} 字分析", file=sys.stderr)
        prompt = (
            f"你是科技短视频主播。请根据以下模型信息和调研结果，写一段40-70字的解说词。\n"
            f"要求：\n"
            f"- 必须说清楚模型名称\n"
            f"- 必须提到它在哪个榜单/领域取得最好成绩（如果有）\n"
            f"- 必须说明相比其他模型的核心亮点\n"
            f"- 语气自信专业，适合短视频配音\n\n"
            f"模型信息：{title}\n补充：{summary[:200]}\n"
            f"深度调研结果：\n{research[:500]}"
        )
    elif abstract or method:
        prompt = (
            f"你是科技短视频主播。请为以下AI论文写一段35-55字的解说词，"
            f"用通俗语言解释核心方法和创新点。\n"
            f"标题：{title}\n"
            f"方法概要：{method or abstract[:300]}"
        )
    else:
        prompt = (
            f"你是科技短视频主播，正在录制具身智能快报第{index}条。\n"
            f"请为以下新闻写一段30-50字的解说词。\n"
            f"要求：语气自信、节奏明快，直接切入内容，"
            f"必须包含具体公司名或产品名，不要套话。\n\n"
            f"标题：{title}\n摘要：{summary[:200]}\n来源：{source}"
        )

    try:
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

    return method or (f"{title}。{summary[:60]}" if summary != title else title)


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
