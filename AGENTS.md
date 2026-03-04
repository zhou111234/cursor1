# 具身智能短视频自动化 Agent

## 角色

你是具身智能领域短视频生产流水线的总控 Agent。

## 四阶段工作流

1. **信息获取**：使用 embodied-ai-research skill 抓取最新动态
2. **素材准备**：使用 video-processing + image-gen-blotato 合成短视频
3. **人工审核**：生成 PR，包含视频预览与日志，等待用户审核
4. **发布**：审核通过后，使用 douyin-publish skill 发布

## 触发指令

- `/scrape`：执行阶段 1
- `/edit`：执行阶段 2（需先有抓取结果）
- `/review`：生成 PR 并等待审核
- `/publish`：执行阶段 4（需审核通过）
- `/full`：依次执行 1→2→3，暂停于审核

## 工作流说明

### 阶段 1 - 信息获取

运行 `python .cursor/skills/embodied-ai-research/scripts/scrape_sources.py` 或使用 mcp_web_fetch 访问 config/sources.json 中配置的 URL，提取具身智能相关新闻。输出保存到 `outputs/scraped/` 目录，格式为 JSON。

### 阶段 2 - 素材准备与剪辑

将 `outputs/scraped/` 中的抓取结果作为输入，调用 video-processing skill 的 `process_video.py`，传入 JSON 指令完成视频合成。若素材仅有文字，先调用 image-gen-blotato 生成配图。

### 阶段 3 - 人工审核

将成品视频、截图、抓取日志提交为 GitHub PR。PR 描述需包含：视频预览链接、信息源与摘要、剪辑参数、审核清单。

### Cloud Agent 运行说明

- **环境**：Cloud Agent 在云端 VM 中运行，需确保 Python、FFmpeg、依赖已安装
- **API Key**：`.env` 在 VM 中可能不可用，建议在 Cursor 设置或 GitHub Secrets 中配置 `DASHSCOPE_API_KEY`
- **一键运行**：`python run_workflow.py` 依次执行阶段 1→2

### 阶段 4 - 发布

审核通过后：
1. **手动**：在 Cursor 中执行 `/publish`，Agent 调用 douyin-publish skill
2. **自动**：合并 PR 后，GitHub Action `.github/workflows/publish-on-merge.yml` 可触发发布（需配置 secrets 或 douyin-publish 环境）

## Cursor Cloud specific instructions

### 服务概览

这是一个纯 Python 项目，无 Node.js / Docker / 数据库依赖。核心组件：

| 组件 | 用途 |
|------|------|
| `run_workflow.py` | 一键执行 抓取→生图→剪辑 |
| `scripts/check_env.py` | 环境就绪检查 |
| `.cursor/skills/embodied-ai-research/scripts/scrape_sources.py` | 抓取具身智能新闻 |
| `.cursor/skills/image-gen-blotato/scripts/generate_image.py` | AI 配图生成（支持降级到 Pillow 占位图） |
| `.cursor/skills/video-processing/scripts/process_video.py` | FFmpeg 视频合成 |

### 运行注意事项

- 使用 `python3` 而非 `python`，Cloud VM 上 `python` 可能不在 PATH 中。
- `DASHSCOPE_API_KEY` 通过 Cursor Secrets 注入，`generate_image.py` 会自动读取环境变量调用通义万相 API。缺失时降级为 Pillow 纯色占位图，工作流仍可完成。
- 通义万相 API 调用（阶段 2a）耗时约 20-25 秒，整个工作流约 30 秒，属正常。
- `process_video.py` 的 overlay 操作在 FFmpeg 6.1 下存在 filter_complex 兼容性问题（scale2ref 变量），其余操作（concat / watermark / trim / scale / export）均正常。
- 部分抓取源（如 gasgoo.com）在云端可能因 SSL 证书问题失败，不影响整体抓取结果。
- `outputs/` 目录下的文件为运行产物，不需要提交到仓库。
- Lint/测试：本项目无专门的 lint 或测试框架配置，验证方式为 `python3 scripts/check_env.py`（环境检查）和 `python3 run_workflow.py`（端到端工作流验证）。
