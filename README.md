# 具身智能短视频自动化工作流

基于 Cursor Cloud Agent 的四阶段工作流：信息抓取 → 视频剪辑 → 人工审核 → 抖音发布。

## 项目结构

```
embodied-ai-video-pipeline/
├── .cursor/skills/          # Agent Skills
├── config/                  # 配置
├── outputs/                 # 输出（草稿、已发布）
├── AGENTS.md               # Cloud Agent 总控指令
└── README.md
```

## 前置依赖

- Python 3.10+
- FFmpeg（视频剪辑）
- Cursor Pro（Cloud Agent）
- 抖音开放平台开发者账号（发布阶段）

## 安装

```bash
pip install requests beautifulsoup4
```

## 使用

1. **信息获取**：`/scrape` 或运行 `python .cursor/skills/embodied-ai-research/scripts/scrape_sources.py`
2. **视频剪辑**：`/edit` 使用 video-processing skill
3. **人工审核**：`/review` 生成 PR
4. **发布**：`/publish` 或合并 PR 触发 GitHub Action

## Skills

| Skill | 用途 |
|-------|------|
| `embodied-ai-research` | 具身智能信息抓取 |
| `video-processing` | 视频剪辑（JSON → FFmpeg） |
| `image-gen-blotato` | 配图生成（Blotato/OpenAI） |
| `douyin-publisher` | 发布指引，需安装 `/learn @openclaw/douyin-publish` |

## GitHub Actions

- `scheduled-scrape.yml`：每日定时抓取（可手动触发）
- `publish-on-merge.yml`：PR 合并后发布占位（需配置 secrets）
