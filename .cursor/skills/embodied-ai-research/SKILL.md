---
name: embodied-ai-research
description: Scrapes web pages for embodied AI and robotics news. Extracts titles, summaries, images, and video URLs. Use when gathering latest embodied intelligence updates, robotics news, or when the user runs /scrape or requests information scraping for video content.
---

# Embodied AI Research Skill

## Purpose

从多个渠道获取具身智能（Embodied AI）、人形机器人领域的最新资讯，输出结构化 JSON 供下游视频生产使用。

## 数据源

| 来源 | 类型 | 说明 |
|------|------|------|
| Perplexity AI | 联网搜索 | 按维度提示词库搜索热点 |
| 机器人公司官网 | 网页抓取 | Boston Dynamics / Figure AI / Unitree 等 |
| HuggingFace | API | SOTA 模型 + 论文（含方法提炼） |
| GitHub Trending | API | 热门 robotics / embodied-ai 仓库 |

## Perplexity 提示词库

提示词库位于 `prompts/perplexity_queries.json`，按 7 个维度组织：

| 维度 | ID | 覆盖范围 |
|------|-----|---------|
| 技术突破 | `tech_breakthrough` | 运动控制、灵巧操作、VLA模型、世界模型 |
| 产品发布 | `product_launch` | 各公司新品、硬件/软件/仿真平台 |
| 投融资 | `funding` | 融资轮次、收购、IPO、估值 |
| 产业落地 | `industry_deployment` | 制造/物流/医疗/家庭场景部署 |
| 政策法规 | `policy` | 中/美/欧/日/韩政策、标准 |
| 开源生态 | `open_source` | 新模型/框架/数据集/仿真工具 |
| 学术前沿 | `academic` | arXiv/ICRA/CoRL/NeurIPS 热门论文 |

### 元提示词

- `daily_digest`: 每日综合情报（8条，覆盖全维度）
- `weekly_roundup`: 每周十大要闻
- `trend_analysis`: 本周3大趋势提炼

### 在 config/sources.json 中使用

```json
{
  "id": "perplexity",
  "type": "perplexity",
  "query_sets": ["daily_digest", "tech_breakthrough", "product_launch"],
  "enabled": true
}
```

`query_sets` 指定使用哪些维度/元提示词，系统会自动从提示词库中选取对应 query。

### 自定义提示词

编辑 `prompts/perplexity_queries.json` 中的 `dimensions` 或 `meta_prompts` 即可扩展。

## Quick Start

```bash
python .cursor/skills/embodied-ai-research/scripts/scrape_sources.py
```

## Output Format

```json
{
  "scraped_at": "2026-03-05T10:30:00Z",
  "items": [
    {
      "title": "标题",
      "summary": "摘要",
      "source": "来源",
      "url": "https://...",
      "paper_url": "https://arxiv.org/abs/...",
      "paper_abstract": "论文完整摘要",
      "method_summary": "LLM提炼的核心方法",
      "image_urls": [],
      "video_urls": [],
      "published_at": "2026-03-05T10:00:00Z"
    }
  ]
}
```
