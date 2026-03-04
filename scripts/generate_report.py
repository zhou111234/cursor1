#!/usr/bin/env python3
"""
根据抓取到的所有内容，调用 LLM 生成今日具身智能行业报告。
输出 Markdown 格式，保存到 outputs/reports/ 目录。
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).resolve().parent.parent
    load_dotenv(_project_root / ".env")
except ImportError:
    pass


def build_prompt(items: list[dict], date_str: str) -> str:
    """将抓取条目组装为 LLM 提示词。"""
    items_text = ""
    for i, item in enumerate(items, 1):
        source = item.get("source", "未知")
        title = item.get("title", "")
        summary = item.get("summary", "")
        url = item.get("url", "")
        has_video = bool(item.get("video_urls"))
        items_text += f"\n{i}. [{source}] {title}\n"
        if summary and summary != title:
            items_text += f"   摘要: {summary[:200]}\n"
        if url:
            items_text += f"   链接: {url}\n"
        if has_video:
            items_text += f"   (含视频)\n"

    prompt = f"""你是具身智能和机器人行业的资深分析师。今天是{date_str}。

以下是今天从多个渠道（新闻网站、YouTube、AI分析）收集到的{len(items)}条具身智能相关信息：

{items_text}

请基于以上信息，生成一份专业的 **《{date_str} 具身智能行业日报》**，严格使用 Markdown 格式，包含以下章节：

## 📋 今日概览
用 2-3 句话总结今天的整体态势。

## 🔥 重点新闻解读
挑选最重要的 3-5 条进行深度解读，每条包含：
- **标题**（加粗）
- 来源与链接
- 100-150 字的分析点评，阐述其行业意义

## 📊 行业趋势分析
从今日信息中提炼 2-3 个趋势方向，每个趋势用 50-80 字说明。

## 🏢 关键企业/机构动态
列出今日涉及的关键企业或机构及其动态（表格形式）。

## 🌐 国内外对比观察
简要对比国内和国际在具身智能领域的侧重点差异。

## 💡 投资与关注建议
给出 2-3 条值得关注的方向或标的建议。

## 📌 明日关注
列出 2-3 个明天值得持续跟踪的话题。

要求：
- 语言：中文
- 语气：专业、客观、有洞察力
- 不要编造抓取内容中没有的公司或事件
- 引用具体信息时标注来源"""

    return prompt


def generate_with_llm(prompt: str, api_key: str) -> str | None:
    """调用通义千问生成报告。"""
    try:
        from dashscope import Generation
    except ImportError:
        print("dashscope not installed", file=sys.stderr)
        return None

    try:
        rsp = Generation.call(
            model="qwen-plus",
            api_key=api_key,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            max_tokens=4000,
        )
    except Exception as e:
        print(f"LLM error: {e}", file=sys.stderr)
        return None

    if rsp.status_code != 200:
        print(f"LLM API error: {getattr(rsp, 'message', rsp)}", file=sys.stderr)
        return None

    return rsp.output.choices[0].message.content


def generate_fallback_report(items: list[dict], date_str: str) -> str:
    """无 API key 时生成简易模板报告。"""
    lines = [
        f"# {date_str} 具身智能行业日报\n",
        f"> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} | 共采集 {len(items)} 条信息\n",
        "## 📋 今日概览\n",
        f"今日共采集到 {len(items)} 条具身智能相关信息，",
    ]

    sources = {}
    for item in items:
        src = item["source"].split(" | ")[0] if " | " in item["source"] else item["source"]
        sources[src] = sources.get(src, 0) + 1
    src_desc = "、".join(f"{k}({v}条)" for k, v in sorted(sources.items(), key=lambda x: -x[1]))
    lines.append(f"来源涵盖 {src_desc}。\n")

    lines.append("\n## 🔥 今日信息列表\n")
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        source = item.get("source", "")
        url = item.get("url", "")
        summary = item.get("summary", "")
        lines.append(f"### {i}. {title}\n")
        lines.append(f"- **来源**: {source}")
        if url:
            lines.append(f"- **链接**: {url}")
        if summary and summary != title:
            lines.append(f"- **摘要**: {summary[:200]}")
        lines.append("")

    lines.append("\n---\n")
    lines.append("*注：未配置 DASHSCOPE_API_KEY，使用模板报告。配置后可获得 AI 深度分析。*\n")
    return "\n".join(lines)


def main():
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    items_path = None
    output_path = None

    if len(sys.argv) >= 2:
        items_path = sys.argv[1]
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    if not items_path:
        scraped_dir = project_root / "outputs" / "scraped"
        files = sorted(scraped_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            print("No scraped data found", file=sys.stderr)
            sys.exit(1)
        items_path = str(files[0])

    with open(items_path, encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("items", [])

    if not items:
        print("No items to report", file=sys.stderr)
        sys.exit(1)

    date_str = datetime.now().strftime("%Y年%m月%d日")

    if not output_path:
        report_dir = project_root / "outputs" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(report_dir / f"report_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if api_key:
        print("调用 AI 分析师生成深度报告...")
        prompt = build_prompt(items, date_str)
        report = generate_with_llm(prompt, api_key)
        if not report:
            print("AI 生成失败，回退到模板报告", file=sys.stderr)
            report = generate_fallback_report(items, date_str)
    else:
        print("DASHSCOPE_API_KEY 未配置，使用模板报告")
        report = generate_fallback_report(items, date_str)

    header = (
        f"# {date_str} 具身智能行业日报\n\n"
        f"> 🤖 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} "
        f"| 数据来源: {len(items)} 条采集信息\n\n---\n\n"
    )

    if not report.startswith("#"):
        full_report = header + report
    else:
        full_report = report

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
