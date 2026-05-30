# AI信息助手 — Claude Code 项目理解

## 项目定位

本地命令行工具，自动抓取全球AI领域最新动态，调用 DeepSeek API（通过 Anthropic 兼容层）翻译摘要生成中文日报/周报，支持开源项目深度拆解和论文精读。

## 技术栈

- **语言**: Python 3.12
- **AI 后端**: DeepSeek V4 Pro（默认，便宜 + 中文强 + 1M 上下文）
- **SDK**: `anthropic` Python SDK（通过 DeepSeek 的 Anthropic 兼容端点）
- **数据存储**: SQLite（去重 + 历史查询）+ JSON 文件缓存
- **配置**: YAML
- **HTTP**: httpx（异步）+ feedparser（RSS）

## 目录结构

```
src/
├── main.py              # CLI 入口 + 定时调度
├── fetchers/            # 各数据源抓取器
├── processor/           # AI 翻译摘要分类
├── deepdive/            # 深度分析（项目拆解 + 论文精读）
├── reporter/            # Markdown 报告生成
└── storage/             # SQLite + 缓存
```

## DeepSeek API 适配要点

⚠️ **关键**：虽然用 Anthropic SDK，但后端是 DeepSeek。

1. **ThinkingBlock 处理**：DeepSeek 返回的 `message.content` 可能包含 `ThinkingBlock`（`.thinking` 属性）和 `TextBlock`（`.text` 属性）。必须遍历过滤出 `TextBlock`，不能直接取 `message.content[0].text`。

```python
for block in message.content:
    if hasattr(block, "text"):
        return block.text
```

2. **模型名**：从环境变量 `ANTHROPIC_MODEL` 读取，默认 `deepseek-v4-pro[1m]`。

3. **成本优势**：DeepSeek 约 ¥0.001/1K tokens，可一次传 3W+ 字符代码做深度分析。

## 代码规范

- 异步优先（`async/await` + `httpx.AsyncClient`）
- 优雅降级（单数据源失败不阻塞整体）
- URL 去重（SQLite `INSERT OR IGNORE`）
- 请求缓存（1-2 小时 TTL）

## 扩展数据源

添加新数据源只需：
1. 在 `src/fetchers/` 新建文件
2. 实现 `async def fetch(...) -> list[dict]`
3. 在 `main.py` 的 `fetch_all()` 中注册
4. 在 `config.yaml` 中添加开关
