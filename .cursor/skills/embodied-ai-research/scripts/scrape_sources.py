#!/usr/bin/env python3
"""
Scrapes configured sources for embodied AI and robotics news.
Outputs structured JSON for downstream video production.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

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
        url = src["url"]
        name = src.get("name", "Unknown")

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

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "items": all_items[:20],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Scraped {len(result['items'])} items -> {out_file}")


if __name__ == "__main__":
    main()
