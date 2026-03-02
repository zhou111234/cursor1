---
name: embodied-ai-research
description: Scrapes web pages for embodied AI and robotics news. Extracts titles, summaries, images, and video URLs. Use when gathering latest embodied intelligence updates, robotics news, or when the user runs /scrape or requests information scraping for video content.
---

# Embodied AI Research Skill

## Purpose

Fetches and extracts content from configured sources about embodied AI (具身智能), humanoid robots, and robotics. Outputs structured JSON for downstream video production.

## Quick Start

1. Load sources from `config/sources.json`
2. For each enabled source, run the scrape script or use mcp_web_fetch
3. Output to `outputs/scraped/YYYY-MM-DD_HH-mm.json`

## Scrape Script

```bash
python .cursor/skills/embodied-ai-research/scripts/scrape_sources.py [--output-dir outputs/scraped]
```

## Output Format

```json
{
  "scraped_at": "2024-01-15T10:30:00Z",
  "items": [
    {
      "title": "Article title",
      "summary": "Brief summary (2-3 sentences)",
      "source": "Source name",
      "url": "https://...",
      "image_urls": ["https://..."],
      "video_urls": [],
      "published_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

## Fallback Strategy

- If `mcp_web_fetch` fails due to network: try requests + BeautifulSoup in script
- If page structure changed: use RSS when available (e.g., arXiv)
- Keywords: 具身智能, embodied AI, 人形机器人, humanoid robot, robotics

## Target Sources (config/sources.json)

- arXiv cs.RO (RSS)
- 新华网科技
- 投中网

Add new sources by updating config/sources.json.
