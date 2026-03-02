---
name: douyin-publisher
description: Publishes approved video drafts to Douyin. Uses OpenClaw douyin-publish (MCP) for login and upload. Use when user approves a PR, runs /publish, or requests video publishing to Douyin after review.
---

# Douyin Publisher Skill

## Prerequisites

Install OpenClaw douyin-publish skill first:

```
/learn @openclaw/douyin-publish
```

## Workflow

1. **After PR approval**: Video draft is in `outputs/drafts/` or PR artifacts
2. **Run publish**: Agent invokes douyin-publish with the approved video path
3. **Session**: douyin-publish maintains login via MCP; may require periodic re-auth

## Video Requirements (Douyin)

- Format: mp4, webm
- Resolution: 720x1280 (9:16) or higher
- Max size: 300MB
- Avoid heavy branding/watermarks (may affect recommendation)

## Project Paths

- Drafts: `outputs/drafts/<video>.mp4`
- Published log: `outputs/published/` (optional metadata)

## Alternative: Douyin Open Platform API

If douyin-publish MCP is unavailable, use official API:

- Endpoint: `POST https://open.douyin.com/api/douyin/v1/video/upload_video/`
- Auth: access-token, open_id (from developer console)
- For files >128MB: use slice upload flow

## Trigger

User says "发布" or "/publish" after approving the review PR.
