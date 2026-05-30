"""
翻译 + 摘要 + 分类处理器
一次 AI API 调用完成三项任务，节省 token（默认 DeepSeek，兼容 Claude）
"""

import os
from anthropic import Anthropic


def _get_client() -> Anthropic:
    """初始化 Anthropic 客户端（通过 DeepSeek 后端）"""
    return Anthropic(
        api_key=os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"),
    )


# ====== Prompt 模板 ======

PAPER_SUMMARY_PROMPT = """你是一位AI领域资深研究员，请用中文总结以下论文：

**标题**: {title}
**作者**: {authors}
**摘要**: {abstract}

请返回严格的JSON格式（不要markdown代码块）：
{{
  "title_cn": "论文中文标题（简洁准确）",
  "one_liner": "一句话核心贡献（30字以内）",
  "key_method": "关键方法/创新点（50字以内）",
  "tags": ["标签1", "标签2"],
  "importance": 1-5的整数评分（5=突破性）
}}

标签请从以下类别中选择：大语言模型, 多模态, 智能体, 具身智能, 计算机视觉, 自然语言处理, 强化学习, 图神经网络, 语音合成, 代码生成, RAG, 推理, 训练, 微调, 安全对齐, 评估基准, 模型压缩, 数据工程, 其他"""


REPO_SUMMARY_PROMPT = """你是一位开源项目分析专家，请用中文分析以下GitHub项目：

**项目名**: {name}
**描述**: {description}
**语言**: {language}
**标签**: {topics}

请返回严格的JSON格式（不要markdown代码块）：
{{
  "name_cn": "项目中文名（如项目名已是中文则保留）",
  "one_liner": "一句话说明这个项目是做什么的（30字以内）",
  "why_matters": "为什么值得关注（40字以内）",
  "tags": ["标签1", "标签2"],
  "difficulty": "入门/中等/进阶",
  "stars_comment": "对star数的简短评价"
}}

标签请从以下选择：Agent框架, LLM工具, RAG, 微调工具, 推理优化, 多模态, 前端UI, DevOps, 数据处理, 评估测试, 其他"""


def _call_ai(prompt: str, max_tokens: int = 2000, temperature: float = 0.3) -> str | None:
    """调用 AI API（DeepSeek/Claude）"""
    try:
        client = _get_client()
        # 通过环境变量取模型名
        model = os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro[1m]")

        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        # DeepSeek 返回的 content 可能包含 ThinkingBlock 和 TextBlock
        # 需要过滤出 TextBlock 获取实际文本
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        # 如果没有 TextBlock，尝试取第一个 block 的内容
        if message.content:
            first = message.content[0]
            if hasattr(first, "thinking"):
                return first.thinking  # 思考过程作为后备
            return str(first)
        return None
    except Exception as e:
        print(f"  ❌ API调用失败: {e}")
        return None


def summarize_papers(papers: list[dict], batch_size: int = 5) -> list[dict]:
    """
    批量翻译+摘要论文
    每批5篇一起调用API，减少请求次数
    返回带 summary 字段的论文列表
    """
    results = []
    total = len(papers)

    for i in range(0, total, batch_size):
        batch = papers[i : i + batch_size]
        print(f"  🧠 正在翻译总结论文 {i+1}-{min(i+batch_size, total)}/{total}...")

        # 构建批量prompt
        papers_text = ""
        for j, p in enumerate(batch):
            papers_text += f"""
---
论文 {j+1}:
标题: {p.get('title', '?')}
作者: {p.get('authors', '?')[:200]}
摘要: {p.get('abstract', '?')[:1000]}
"""

        prompt = f"""你是一位AI领域资深研究员，请用中文逐一总结以下论文。

对每篇论文，返回严格的JSON格式（不要markdown代码块，返回一个JSON数组）：

{{
  "index": 论文序号,
  "title_cn": "论文中文标题",
  "one_liner": "一句话核心贡献（30字以内）",
  "key_method": "关键方法/创新点（50字以内）",
  "tags": ["标签1", "标签2"],
  "importance": 1-5的整数评分
}}

标签可从：大语言模型, 多模态, 智能体(Agent), 具身智能, 计算机视觉, NLP, 强化学习, 图神经网络, 语音/音频, 代码生成, RAG, 推理, 训练方法, 模型微调, 安全对齐, 评估基准, 模型压缩, 数据工程, 其他 中选择。

论文列表：
{papers_text}

请返回JSON数组（严格JSON，无markdown代码块包裹）："""

        response = _call_ai(prompt, max_tokens=4000)
        if not response:
            # API失败，返回原文信息
            for j, p in enumerate(batch):
                p["summary"] = {
                    "title_cn": p.get("title", ""),
                    "one_liner": p.get("abstract", "")[:60] + "...",
                    "key_method": "（API故障，请重试）",
                    "tags": ["其他"],
                    "importance": 2,
                }
                results.append(p)
            continue

        # 解析JSON数组
        import json
        try:
            # 清理可能的markdown包裹
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
                if response.endswith("```"):
                    response = response[:-3]
            summaries = json.loads(response)
            if isinstance(summaries, dict):
                summaries = [summaries]

            for j, p in enumerate(batch):
                summary = next((s for s in summaries if s.get("index") == j + 1), summaries[j] if j < len(summaries) else {})
                p["summary"] = summary
                results.append(p)
        except (json.JSONDecodeError, IndexError) as e:
            print(f"  ⚠️ JSON解析失败: {e}，使用原文")
            for j, p in enumerate(batch):
                p["summary"] = {
                    "title_cn": p.get("title", ""),
                    "one_liner": p.get("abstract", "")[:60] + "...",
                    "key_method": "（解析失败）",
                    "tags": ["其他"],
                    "importance": 2,
                }
                results.append(p)

    return results


def summarize_repos(repos: list[dict]) -> list[dict]:
    """
    批量分析开源项目
    返回带 summary 字段的项目列表
    """
    results = []
    total = len(repos)
    batch_size = 5

    for i in range(0, total, batch_size):
        batch = repos[i : i + batch_size]
        print(f"  🧠 正在分析项目 {i+1}-{min(i+batch_size, total)}/{total}...")

        repos_text = ""
        for j, r in enumerate(batch):
            repos_text += f"""
---
项目 {j+1}:
名称: {r.get('name', '?')}
描述: {r.get('description', '?')[:300]}
语言: {r.get('language', '?')}
标签: {r.get('topics', '?')[:200]}
"""

        prompt = f"""你是一位开源项目分析专家，请用中文逐一分析以下GitHub项目。

对每个项目返回严格JSON（返回JSON数组）：

{{
  "index": 项目序号,
  "name_cn": "项目中文名/描述",
  "one_liner": "一句话说明这个项目有什么用（30字以内）",
  "why_matters": "为什么值得关注（40字以内）",
  "tags": ["标签1", "标签2"],
  "difficulty": "入门/中等/进阶"
}}

标签可从：Agent框架, LLM工具/应用, RAG/检索, 微调工具, 推理优化, 多模态, 前端/UI, DevOps/部署, 数据处理, 评估/测试, 其他 中选择。

项目列表：
{repos_text}

请返回JSON数组（严格JSON，无markdown代码块包裹）："""

        response = _call_ai(prompt, max_tokens=3000)
        if not response:
            for j, r in enumerate(batch):
                r["summary"] = {
                    "name_cn": r.get("name", ""),
                    "one_liner": (r.get("description") or "")[:60] + "...",
                    "why_matters": "（API故障）",
                    "tags": ["其他"],
                    "difficulty": "入门",
                }
                results.append(r)
            continue

        import json
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
                if response.endswith("```"):
                    response = response[:-3]
            summaries = json.loads(response)
            if isinstance(summaries, dict):
                summaries = [summaries]

            for j, r in enumerate(batch):
                summary = next((s for s in summaries if s.get("index") == j + 1), summaries[j] if j < len(summaries) else {})
                r["summary"] = summary
                results.append(r)
        except (json.JSONDecodeError, IndexError) as e:
            print(f"  ⚠️ JSON解析失败: {e}")
            for j, r in enumerate(batch):
                r["summary"] = {
                    "name_cn": r.get("name", ""),
                    "one_liner": (r.get("description") or "")[:60] + "...",
                    "why_matters": "（解析失败）",
                    "tags": ["其他"],
                    "difficulty": "入门",
                }
                results.append(r)

    return results
