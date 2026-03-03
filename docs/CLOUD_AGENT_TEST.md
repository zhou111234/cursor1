# Cursor Cloud Agent 云端测试指南

## 测试步骤

### 1. 从 GitHub 克隆项目（模拟 Cloud Agent 环境）

```bash
git clone https://github.com/zhou111234/cursor1.git
cd cursor1
```

### 2. 在 Cursor 中打开项目

- File → Open Folder → 选择 `cursor1` 目录
- 或使用 Cursor 的「Clone from GitHub」从 `zhou111234/cursor1` 克隆

### 3. 配置 API Key（Cloud Agent 必须）

Cloud Agent 的 VM 无法读取本地 `.env`，需在对话中告知 Agent：

```
请设置环境变量 DASHSCOPE_API_KEY=sk-ded384a06c754c8fa396e56ff9d8b221 后执行工作流
```

或在 Cursor Settings → Features → Environment 中配置（若支持）。

### 4. 触发 Cloud Agent 执行

在 Cursor 对话中输入：

```
执行完整工作流：先运行 pip install -r requirements.txt，再运行 python run_workflow.py
```

或分步：

```
1. pip install -r requirements.txt
2. python scripts/check_env.py   # 检查环境
3. python run_workflow.py        # 执行工作流
```

### 5. 验证结果

- `outputs/scraped/` 应有最新 JSON
- `outputs/drafts/` 应有配图和视频

## 环境要求

Cloud Agent VM 通常已具备：
- Python 3.x
- 可能需安装：`pip install -r requirements.txt`
- FFmpeg：若缺失，Agent 需执行 `apt-get install ffmpeg`（Linux）或等效命令

## 快速环境检查

```bash
python scripts/check_env.py
```

输出应全部为 `[OK]`。
