#!/usr/bin/env python3
"""
Scrapes configured sources for embodied AI and robotics news.
Supports web pages, YouTube search, and LLM topic generation.
Outputs structured JSON for downstream video production.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, quote

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install: pip install requests beautifulsoup4", file=sys.stderr)
    sys.exit(1)


def load_config(config_path: Path) -> dict:
    """Load sources config."""
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch URL content."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Fetch failed {url}: {e}", file=sys.stderr)
        return None


def extract_arxiv(html: str, base_url: str) -> list[dict]:
    """Extract items from arXiv list page."""
    items = []
    soup = BeautifulSoup(html, "html.parser")
    for dl in soup.find_all("dl"):
        for dt in dl.find_all("dt"):
            link = dt.find("a", title="Abstract")
            if not link:
                continue
            title = link.get("title", "").strip() or link.get_text(strip=True)
            if not title:
                continue
            href = link.get("href", "")
            if href.startswith("/"):
                href = "https://arxiv.org" + href
            items.append({
                "title": title[:200],
                "summary": title[:300],
                "source": "arXiv cs.RO",
                "url": href,
                "image_urls": [],
                "video_urls": [],
                "published_at": datetime.now(timezone.utc).isoformat(),
            })
    return items[:10]


def extract_generic(html: str, url: str, source_name: str) -> list[dict]:
    """Extract items from generic news page."""
    items = []
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href or href.startswith("#") or "javascript" in href:
            continue
        full_url = urljoin(url, href)
        text = a.get_text(strip=True)
        if len(text) < 10 or len(text) > 150:
            continue
        img = a.find("img")
        img_url = img.get("src", "") if img else ""
        if img_url:
            img_url = urljoin(url, img_url)
        items.append({
            "title": text[:200],
            "summary": text[:300],
            "source": source_name,
            "url": full_url,
            "image_urls": [img_url] if img_url else [],
            "video_urls": [],
            "published_at": datetime.now(timezone.utc).isoformat(),
        })
    seen = set()
    unique = []
    for it in items:
        key = it["url"]
        if key not in seen:
            seen.add(key)
            unique.append(it)
    return unique[:15]


def extract_youtube(query: str, source_name: str = "YouTube", max_results: int = 10) -> list[dict]:
    """Search YouTube and extract video titles as news items."""
    url = f"https://www.youtube.com/results?search_query={quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"YouTube fetch failed: {e}", file=sys.stderr)
        return []

    match = re.search(r"var ytInitialData = ({.*?});", r.text)
    if not match:
        print("YouTube: ytInitialData not found", file=sys.stderr)
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        print("YouTube: JSON parse error", file=sys.stderr)
        return []

    items = []
    contents = (
        data.get("contents", {})
        .get("twoColumnSearchResultsRenderer", {})
        .get("primaryContents", {})
        .get("sectionListRenderer", {})
        .get("contents", [])
    )
    for section in contents:
        for entry in section.get("itemSectionRenderer", {}).get("contents", []):
            vid = entry.get("videoRenderer", {})
            if not vid:
                continue
            title = vid.get("title", {}).get("runs", [{}])[0].get("text", "")
            if not title:
                continue
            vid_id = vid.get("videoId", "")
            channel = vid.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
            desc_parts = vid.get("detailedMetadataSnippets", [{}])
            summary = ""
            if desc_parts:
                snippet_runs = desc_parts[0].get("snippetText", {}).get("runs", [])
                summary = "".join(r.get("text", "") for r in snippet_runs)

            items.append({
                "title": title[:200],
                "summary": (summary or title)[:300],
                "source": f"{source_name} | {channel}" if channel else source_name,
                "url": f"https://www.youtube.com/watch?v={vid_id}" if vid_id else "",
                "image_urls": [],
                "video_urls": [f"https://www.youtube.com/watch?v={vid_id}"] if vid_id else [],
                "published_at": datetime.now(timezone.utc).isoformat(),
            })
            if len(items) >= max_results:
                break
        if len(items) >= max_results:
            break

    return items


def generate_llm_topics(api_key: str, num_topics: int = 5) -> list[dict]:
    """Use DashScope Qwen to generate trending embodied AI topics."""
    try:
        from dashscope import Generation
    except ImportError:
        print("LLM topics: dashscope not installed", file=sys.stderr)
        return []

    today = datetime.now().strftime("%Y年%m月%d日")
    prompt = (
        f"你是具身智能和机器人行业的资深分析师。今天是{today}。"
        f"请生成{num_topics}个当前国内外最热门的具身智能/人形机器人话题，"
        "涵盖技术突破、产业动态、政策法规、投融资、应用落地等多个维度。"
        "每个话题要具体、有新闻价值，带有具体的公司名或技术名。"
        '严格按JSON数组格式输出，每个元素包含 "title" 和 "summary" 字段，不要有其他内容。'
    )
    try:
        rsp = Generation.call(
            model="qwen-turbo",
            api_key=api_key,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
        )
    except Exception as e:
        print(f"LLM generation failed: {e}", file=sys.stderr)
        return []

    if rsp.status_code != 200:
        print(f"LLM API error: {getattr(rsp, 'message', rsp)}", file=sys.stderr)
        return []

    content = rsp.output.choices[0].message.content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        topics = json.loads(content)
    except json.JSONDecodeError:
        print(f"LLM JSON parse error: {content[:200]}", file=sys.stderr)
        return []

    items = []
    for t in topics:
        title = t.get("title", "")
        summary = t.get("summary", "")
        if not title:
            continue
        items.append({
            "title": title[:200],
            "summary": (summary or title)[:300],
            "source": "AI分析 (通义千问)",
            "url": "",
            "image_urls": [],
            "video_urls": [],
            "published_at": datetime.now(timezone.utc).isoformat(),
        })

    return items


def fetch_huggingface(max_models: int = 5, max_papers: int = 5) -> list[dict]:
    """从 Hugging Face 获取热门 SOTA 模型和最新论文。"""
    items = []

    # 1) Trending models
    try:
        r = requests.get(
            "https://huggingface.co/api/models",
            params={"sort": "likes7d", "direction": "-1", "limit": max_models},
            headers={"User-Agent": "embodied-ai-pipeline/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        for m in r.json():
            model_id = m.get("id", "")
            if not model_id:
                continue
            author = model_id.split("/")[0] if "/" in model_id else ""
            downloads = m.get("downloads", 0)
            likes = m.get("likes", 0)
            task = m.get("pipeline_tag", "")
            dl_str = f"{downloads/1000:.0f}K" if downloads >= 1000 else str(downloads)
            summary = f"🔥 热门模型 | 任务: {task} | 下载: {dl_str} | 点赞: {likes}"
            items.append({
                "title": f"HuggingFace 热门模型: {model_id}",
                "summary": summary,
                "source": f"HuggingFace | {author}",
                "url": f"https://huggingface.co/{model_id}",
                "image_urls": [],
                "video_urls": [],
                "published_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"HuggingFace models fetch failed: {e}", file=sys.stderr)

    # 2) Daily papers
    try:
        r = requests.get(
            "https://huggingface.co/api/daily_papers",
            params={"limit": max_papers},
            headers={"User-Agent": "embodied-ai-pipeline/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        for p in r.json():
            paper = p.get("paper", {})
            title = paper.get("title", "")
            if not title:
                continue
            paper_id = paper.get("id", "")
            summary = paper.get("summary", "")[:200]
            upvotes = p.get("paper", {}).get("upvotes", 0)
            items.append({
                "title": f"HF论文: {title}",
                "summary": summary if summary else title,
                "source": "HuggingFace Papers",
                "url": f"https://huggingface.co/papers/{paper_id}" if paper_id else "",
                "image_urls": [],
                "video_urls": [],
                "published_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"HuggingFace papers fetch failed: {e}", file=sys.stderr)

    return items


def main():
    script_path = Path(__file__).resolve()
    # scripts/ -> embodied-ai-research/ -> skills/ -> .cursor/ -> project_root
    project_root = script_path.parent.parent.parent.parent.parent
    config_path = project_root / "config" / "sources.json"
    output_dir = project_root / "outputs" / "scraped"

    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = Path(sys.argv[idx + 1])

    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)
    keywords = config.get("keywords", [])
    all_items = []

    for src in config.get("sources", []):
        if not src.get("enabled", True):
            continue
        source_type = src.get("type", "web")
        url = src.get("url", "")
        name = src.get("name", "Unknown")

        if source_type == "huggingface":
            print(f"  HuggingFace: 获取热门模型和论文...", file=sys.stderr)
            hf_items = fetch_huggingface(
                max_models=src.get("max_models", 5),
                max_papers=src.get("max_papers", 5),
            )
            all_items.extend(hf_items)
            continue

        if source_type == "youtube":
            queries = src.get("queries", keywords[:3])
            for q in queries:
                print(f"  YouTube search: {q}", file=sys.stderr)
                yt_items = extract_youtube(q, source_name=name,
                                           max_results=src.get("max_results", 8))
                all_items.extend(yt_items)
            continue

        if source_type == "llm":
            api_key = os.environ.get("DASHSCOPE_API_KEY")
            if not api_key:
                print("LLM source skipped: DASHSCOPE_API_KEY not set", file=sys.stderr)
                continue
            print(f"  LLM generating topics...", file=sys.stderr)
            llm_items = generate_llm_topics(api_key, num_topics=src.get("num_topics", 5))
            all_items.extend(llm_items)
            continue

        html = fetch_url(url)
        if not html:
            continue

        if "arxiv" in url.lower():
            items = extract_arxiv(html, url)
        else:
            items = extract_generic(html, url, name)

        for item in items:
            title_lower = (item.get("title", "") + item.get("summary", "")).lower()
            if any(kw.lower() in title_lower for kw in keywords):
                all_items.append(item)

    seen_titles = set()
    by_source: dict[str, list[dict]] = {}
    for item in all_items:
        key = item["title"][:50].lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        src_key = item["source"].split(" | ")[0] if " | " in item["source"] else item["source"]
        by_source.setdefault(src_key, []).append(item)

    balanced: list[dict] = []
    max_items = 20
    round_idx = 0
    while len(balanced) < max_items:
        added = False
        for src_items in by_source.values():
            if round_idx < len(src_items) and len(balanced) < max_items:
                balanced.append(src_items[round_idx])
                added = True
        if not added:
            break
        round_idx += 1

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "items": balanced,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Scraped {len(result['items'])} items -> {out_file}")


if __name__ == "__main__":
    main()
