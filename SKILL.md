---
name: ai-news
description: AI信息助手 — 抓取全球AI领域最新论文、开源项目、行业动态，DeepSeek翻译总结生成中文日报，支持项目架构拆解和论文精读。
argument-hint: [daily | weekly | deepdive --repo <url> | deepdive --paper <url>]
allowed-tools: Bash(*), Read, Write, Glob, WebFetch
---

# /ai-news — AI信息助手

自动抓取 arXiv、HuggingFace Papers、GitHub、HackerNews、量子位等数据源，调用 DeepSeek API 翻译摘要生成中文报告，支持开源项目深度拆解和论文精读。

## 触发方式

用户在对话中说以下任意一句即可触发：

| 触发词 | 执行动作 |
|--------|----------|
| "AI日报" "今天有什么AI新闻" "AI资讯" "AI动态" | `daily` |
| "AI周报" "本周AI总结" "这周AI动态" | `weekly` |
| "分析这个项目 https://github.com/xxx" "帮我拆解 xxx 项目" | `deepdive --repo <url>` |
| "精读这篇论文 https://arxiv.org/abs/xxx" "分析这篇论文" | `deepdive --paper <url>` |
| "开启AI日报定时" "每天自动跑AI日报" | `schedule` |
| "查看AI助手配置" "AI助手数据源" | `config` |

## 调用协议

### daily / weekly

```bash
cd <项目目录> && python src/main.py daily
# 或通过虚拟环境: .venv/Scripts/python src/main.py daily (Windows)
#                .venv/bin/python src/main.py daily (Linux/Mac)
```

执行完后，告诉用户报告路径，并摘要报告中的 Top 3 论文和 Top 3 项目。

### deepdive --repo <url>

```bash
cd <项目目录> && python src/main.py deepdive --repo <url>
```

执行完后告诉用户深度分析报告路径。重点提及：
- 架构图（Mermaid）
- 工作流步骤数
- 综合评价

### deepdive --paper <url>

```bash
cd <项目目录> && python src/main.py deepdive --paper <arxiv_url>
```

执行完后告诉用户精读报告路径。重点提及：
- 五维评分
- 方法流程
- 核心洞察

## 项目目录

默认安装路径为用户克隆项目的目录，调用前自动检测。

调用前先确认项目目录存在，如不存在则提示用户：
```
未找到 AI信息助手项目。请先安装：
git clone https://github.com/Yyyy614/ai-info-assistant.git
cd ai-info-assistant
python -m venv .venv && pip install -r requirements.txt
```

## 注意事项

- 工具默认使用 **DeepSeek API**（通过 Anthropic 兼容层），不是原生 Claude API
- API key 从环境变量 `ANTHROPIC_AUTH_TOKEN` 读取
- HuggingFace Papers 数据源需要 VPN，不通时自动跳过
- 报告输出在 `output/` 目录下
- 如数据源全部失败，提示用户检查网络或 VPN 状态
