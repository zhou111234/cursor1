---
name: video-processing
description: Processes video with FFmpeg via JSON instructions. Supports concat, overlay, watermark, trim, scale, and export. Use when editing videos, synthesizing clips, adding watermarks, or when the user runs /edit or requests video production from scraped content.
---

# Video Processing Skill

## Purpose

Executes video operations defined in JSON. Each operation maps to FFmpeg commands. Output format optimized for Douyin (9:16, 720x1280, mp4).

## Quick Start

```bash
python .cursor/skills/video-processing/scripts/process_video.py <instructions.json> [--output output.mp4]
```

## JSON Instruction Format

```json
{
  "ops": [
    {"type": "concat", "inputs": ["intro.mp4", "demo_clip.mp4"]},
    {"type": "overlay", "image": "generated_illustration.png", "position": "top-right"},
    {"type": "watermark", "text": "@your_account"},
    {"type": "scale", "width": 720, "height": 1280},
    {"type": "trim", "start": 0, "end": 30},
    {"type": "export", "format": "mp4", "resolution": "720x1280"}
  ]
}
```

## Supported Operations

| type | params | Description |
|------|--------|-------------|
| concat | inputs: string[] | Concatenate videos (same codec) |
| overlay | image, position | Overlay image on video |
| watermark | text | Add text watermark |
| scale | width, height | Resize to target resolution |
| trim | start, end | Trim by seconds |
| export | format, resolution | Final export |

## Douyin Specs

- Resolution: 720x1280 (9:16)
- Format: mp4 (H.264 + AAC)
- Max size: 300MB

## Prerequisites

- FFmpeg in PATH
- Input files must exist in project or outputs/
