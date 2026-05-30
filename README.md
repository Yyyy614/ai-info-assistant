# 🧠 AI信息助手

> 自动抓取全球AI领域最新论文、开源项目、行业动态，AI翻译总结生成中文日报，支持项目/论文深度拆解。

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![DeepSeek](https://img.shields.io/badge/AI-DeepSeek%20V4-green.svg)](https://deepseek.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 特性

- 📄 **5大数据源** — arXiv · HuggingFace Papers · GitHub Trending · HackerNews · 量子位
- 🤖 **AI翻译摘要** — 标题+摘要中文化、自动分类打标签、重要性评分
- 🔬 **项目拆解** — `git clone` → 读代码 → AI输出架构图+工作流+代码亮点
- 📖 **论文精读** — HTML全文提取 → 方法拆解 → 实验解读 → 五维评分
- ⏰ **定时任务** — 工作日早9点自动生成日报
- 💾 **去重存储** — SQLite 持久化，URL 去重，支持趋势对比

## 📸 效果预览

### 日报

```markdown
### 1. YoCausal：从因果视角看视频生成离世界模型有多远？
⭐⭐⭐⭐⭐ 计算机视觉 | 多模态 | 推理
> 构建基于现实视频的双层因果基准，揭示视频模型感知时间箭头不等于理解因果性。
关键方法: 利用时间反转的现实视频作为自然反事实样本…

### 3. AutoGPT - 自主AI代理框架
⭐ 184,647 | 🔧 Python | Agent框架 | 📊 进阶
> 构建自主AI代理的流行框架，让LLM自主完成复杂任务。
```

### 项目深度分析

```
🏗️ 架构图 → Mermaid flowchart
🔄 工作流 → 6步骤（含命令/输入/输出）
💡 代码亮点 → 关键文件逐行点评
📊 综合评价 → 优点/不足/适合人群
```

### 论文精读

```
📊 评分: 创新性★★★★★ 严谨性★★★★★ 影响力★★★★★
🔧 方法流程: 步骤1→步骤2→步骤3
💡 核心洞察: 感知时间箭头≠理解因果关系
```

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Git
- [DeepSeek API Key](https://platform.deepseek.com/)（推荐，便宜且中文更强）
- 如需原生 Claude：替换环境变量中的 base_url 为 `https://api.anthropic.com`，模型改为 `claude-sonnet-4-6` 等

### 安装

```bash
# 克隆项目
git clone https://github.com/Yyyy614/ai-info-assistant.git
cd ai-info-assistant

# 创建虚拟环境
python -m venv .venv

# 安装依赖（国内用户可用清华源加速）
# Windows
.venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Linux/Mac
.venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 配置

```bash
# 设置 DeepSeek API（推荐）
# 方式1：环境变量（当前终端生效）
export ANTHROPIC_AUTH_TOKEN="sk-你的DeepSeek-key"
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_MODEL="deepseek-v4-pro[1m]"

# 方式2：写入 ~/.claude/settings.json（Claude Code 用户自动读取）
```

```bash
# 复制配置文件
cp config.yaml.example config.yaml
# 按需修改数据源开关、报告设置等
```

### 使用

```bash
# 生成日报
python src/main.py daily

# 生成周报
python src/main.py weekly

# 深度分析 GitHub 项目
python src/main.py deepdive --repo https://github.com/langgenius/dify

# 精读论文
python src/main.py deepdive --paper https://arxiv.org/abs/2605.30346

# 启动定时任务（工作日早9点）
python src/main.py schedule

# 查看配置
python src/main.py config
```

**Windows 用户**：双击 `run.bat` 也可运行。

## 🤖 为什么默认用 DeepSeek？

| 对比 | DeepSeek V4 | Claude (Anthropic) |
|------|:-----------:|:------------------:|
| 💰 成本 | 约 ¥0.001/1K tokens | 约 ¥0.11/1K tokens |
| 🇨🇳 中文学术翻译 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 📏 上下文窗口 | 1M tokens | 200K tokens |
| 🔧 项目拆解能力 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 日常翻译摘要 | ✅ 完全够用 | ✅ |

> **推荐策略**：日常全部用 DeepSeek（1M 上下文一次读完项目代码，中文翻译质量高，成本极低）。极少情况需要更强推理时可切 Claude。

## 📊 数据源

| 源 | 内容 | 需要VPN |
|------|------|:---:|
| arXiv | 最新AI论文（cs.AI/CL/CV/LG/RO） | ❌ |
| HuggingFace Papers | 每日趋势论文 | ✅ |
| GitHub | 热门AI开源项目 | ❌ |
| HackerNews | AI相关高赞讨论 | ❌ |
| 量子位 | 中文AI资讯 | ❌ |

> VPN 策略：HF Papers 等源不通时会自动跳过并提示，不影响整体流程。

## 🏗️ 架构

```
src/
├── main.py              # 入口（CLI + 定时调度）
├── fetchers/            # 数据抓取层
│   ├── arxiv.py         #   arXiv API
│   ├── github.py        #   GitHub API
│   ├── paperswithcode.py #  HuggingFace Papers
│   ├── hackernews.py    #   HackerNews Algolia API
│   └── cn_sources.py    #   量子位 RSS
├── processor/           # 处理层
│   └── summarizer.py    #   DeepSeek翻译+摘要+分类
├── deepdive/            # 深度分析层
│   ├── repo_analyzer.py #   项目架构拆解
│   └── paper_digger.py  #   论文精读
├── reporter/            # 报告输出层
│   └── markdown_reporter.py
└── storage/             # 存储层
    ├── sqlite_store.py  #   SQLite持久化
    └── cache.py         #   请求缓存
```

## 📝 命令参考

| 命令 | 说明 |
|------|------|
| `daily` | 抓取今日数据 → AI翻译 → 生成日报 |
| `weekly` | 7天数据 → 生成周报 |
| `deepdive --repo <url>` | 克隆仓库 → 读代码 → 输出架构+工作流 |
| `deepdive --paper <url>` | 获取论文全文 → 方法拆解 → 五维评分 |
| `schedule` | 启动定时任务（工作日 09:00） |
| `config` | 查看当前配置 |

## 🔌 Claude Code Skill

本工具可注册为 Claude Code Skill，通过对话直接调用：

```bash
# 安装 skill
cp SKILL.md ~/.claude/skills/ai-news/SKILL.md
```

安装后在 Claude Code 中直接说：
- "AI日报" → 自动跑 daily
- "分析这个项目 https://github.com/xxx" → 自动跑 deepdive
- "精读这篇论文 https://arxiv.org/abs/xxx" → 自动跑 paper deepdive

### Claude Code 配置（settings.json）

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-你的DeepSeek-key",
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]"
  }
}
```

## 📄 许可

MIT License — 详见 [LICENSE](LICENSE)
