---
name: image-gen-blotato
description: Generates illustrations from text for embodied AI content. Uses Blotato API or fallback image APIs when source has only text. Use when scraped content lacks images, when user runs /edit with text-only material, or when visual enhancement is needed for video production.
---

# Image Gen Blotato Skill

## Purpose

When scraped embodied AI news has only text, this skill generates配图/示意图 for video production. Integrates with Blotato or configurable image APIs.

## Quick Start

```bash
python .cursor/skills/image-gen-blotato/scripts/generate_image.py "具身智能机器人抓取物体" --output outputs/drafts/illustration.png
```

## Prompt Template (Embodied AI)

For embodied AI / robotics content, use prompts like:

- "科技感示意图：{title}，简约风格，蓝色主调"
- "人形机器人在实验室中{action}，专业摄影风格"
- "Embodied AI concept art: {summary}, modern tech aesthetic"

## Configuration

**通义万相（默认）**：在阿里云控制台获取 API Key，设置环境变量：
```powershell
$env:DASHSCOPE_API_KEY = "sk-xxxx"
```

**地域 Base URL**（若 Key 所属地域非默认）：在 `config/image_gen.json` 的 `tongyi.base_url` 中配置，例如：
- 华北2（北京）标准 API：`https://dashscope.aliyuncs.com/api/v1`
- 或通过环境变量：`$env:DASHSCOPE_HTTP_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"`

Script reads from `config/image_gen.json`:

```json
{
  "provider": "blotato",
  "blotato": {
    "endpoint": "https://api.blotato.com/v1/images",
    "template_id": "default"
  },
  "fallback": "openai",
  "openai_api_key_env": "OPENAI_API_KEY"
}
```

## When to Use

- Scraped item has empty `image_urls`
- User requests "生成配图" or "visual enhancement"
- Video edit step needs illustration for text-only segment

## Output

Saves PNG to specified path. Use as overlay in video-processing skill.
