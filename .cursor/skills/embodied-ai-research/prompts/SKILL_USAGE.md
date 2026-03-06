# Perplexity 情报引擎 — Cursor Skill 使用规范

## 触发条件

当 agent 执行以下操作时，**必须**加载 `perplexity_queries.json` 提示词库：

1. 用户执行 `/scrape` 命令
2. 运行 `python3 run_workflow.py`（任意模式）
3. 直接运行 `scrape_sources.py`
4. 用户要求"抓取最新资讯"、"搜索热点"、"获取情报"

## 提示词选择策略

### 日常运行（默认）

使用 `config/sources.json` 中配置的 `query_sets`：

```json
"query_sets": ["daily_digest", "tech_breakthrough", "dexterous_hand_spec"]
```

### 按需切换维度

在 `config/sources.json` 的 `query_sets` 中替换 ID 即可：

| 场景 | 推荐 query_sets |
|------|----------------|
| 每日快讯 | `["daily_digest"]` |
| 技术深度 | `["tech_breakthrough", "academic", "open_source"]` |
| 商业分析 | `["funding", "industry_deployment", "competitive_landscape"]` |
| 供应链追踪 | `["dexterous_hand_spec", "edge_compute_spec", "power_thermal_spec"]` |
| 全景扫描 | `["daily_digest", "trend_analysis", "reality_check"]` |
| 材料前沿 | `["bionic_material_spec", "sim_to_real_spec"]` |

### 维度 ID 完整列表

| ID | 维度 |
|-----|------|
| `tech_breakthrough` | 技术突破 |
| `product_launch` | 产品发布 |
| `funding` | 投融资 |
| `industry_deployment` | 产业落地 |
| `policy` | 政策法规 |
| `open_source` | 开源生态 |
| `academic` | 学术前沿 |
| `dexterous_hand_spec` | 灵巧手专项 |
| `edge_compute_spec` | 端侧推理芯片 |
| `power_thermal_spec` | 动力与热管理 |
| `sim_to_real_spec` | 仿真与数字孪生 |
| `bionic_material_spec` | 仿生材料与柔性结构 |
| `daily_digest` | 每日综合情报 |
| `weekly_roundup` | 每周十大要闻 |
| `trend_analysis` | 趋势提炼 |
| `competitive_landscape` | 竞争格局 |
| `reality_check` | 批判性审查 |

## 输出字段说明

每条情报包含以下字段（Perplexity 返回后自动解析）：

| 字段 | 说明 |
|------|------|
| `title` | 标题（≤80字，含命名实体） |
| `summary` | 摘要（含日期、量化数据） |
| `validation_type` | 论文/官方发布/Demo/泄露/政策 |
| `technical_readiness` | 研究/实验室Demo/试点/量产 |
| `is_autonomous` | 自主/遥操作/混合 |
| `info_weight` | A(原始源)/B(主流媒体)/C(二级)/D(未验证) |
| `market_impact` | 1-10 影响力评分 |

## 信息权重过滤

- `info_weight: D` + `confidence: low` 的条目会被**自动丢弃**
- 7天以上旧闻标注为 `[OLD NEWS RE-SURFACED]`
- 纯营销内容被 system_role 约束排除
