"""
论文精读器
- 通过 arXiv API / HTML 获取论文全文
- DeepSeek 深度分析：方法拆解、实验解读、启示
- 输出结构化中文精读报告
"""

import os
import re
import httpx
import feedparser
from pathlib import Path
from datetime import datetime
from anthropic import Anthropic

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "deepdive"


def _get_client() -> Anthropic:
    return Anthropic(
        api_key=os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"),
    )


def _call_ai(prompt: str, max_tokens: int = 6000) -> str | None:
    """调用 DeepSeek API"""
    try:
        client = _get_client()
        model = os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro[1m]")
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        return None
    except Exception as e:
        print(f"  ❌ API调用失败: {e}")
        return None


def _extract_arxiv_id(url_or_id: str) -> str:
    """从 arXiv URL 提取 ID"""
    # 匹配 arxiv.org/abs/XXXX.XXXXX 或 arxiv.org/pdf/XXXX.XXXXX
    match = re.search(r'arxiv\.org/(?:abs|pdf)/([\d.]+(?:v\d+)?)', url_or_id)
    if match:
        return match.group(1)
    # 可能是纯 ID
    if re.match(r'^[\d.]+(?:v\d+)?$', url_or_id):
        return url_or_id
    return ""


async def _fetch_arxiv_metadata(arxiv_id: str) -> dict | None:
    """通过 arXiv API 获取论文元数据"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://export.arxiv.org/api/query",
                params={
                    "id_list": arxiv_id,
                    "max_results": "1",
                },
                headers={"User-Agent": "AI-Info-Assistant/1.0"},
            )
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        if not feed.entries:
            return None

        entry = feed.entries[0]
        authors = ", ".join(a.get("name", "") for a in entry.get("authors", []))
        return {
            "arxiv_id": arxiv_id,
            "title": entry.get("title", "").strip().replace("\n", " "),
            "authors": authors,
            "abstract": entry.get("summary", "").strip().replace("\n", " "),
            "published": entry.get("published", "")[:10],
            "category": entry.get("arxiv_primary_category", {}).get("term", ""),
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        }

    except Exception as e:
        print(f"  ⚠️ arXiv 元数据获取失败: {e}")
        return None


async def _fetch_html_fulltext(arxiv_id: str) -> str | None:
    """尝试获取 arXiv HTML 全文"""
    clean_id = arxiv_id.split("v")[0]
    html_url = f"https://arxiv.org/html/{clean_id}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(html_url, headers={"User-Agent": "AI-Info-Assistant/1.0"})
            if resp.status_code != 200:
                return None

            # 简单清理 HTML 标签，提取文本
            html = resp.text
            # 移除 script 和 style
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            # 移除 HTML 标签
            text = re.sub(r'<[^>]+>', ' ', html)
            # 清理空白
            text = re.sub(r'\s+', ' ', text).strip()
            # 限制长度
            if len(text) > 30000:
                text = text[:30000] + "\n... (全文过长，已截取前30000字符)"
            return text
    except Exception:
        return None


def _build_analysis_prompt(metadata: dict, fulltext: str | None) -> str:
    """构建论文精读 prompt"""
    fulltext_section = ""
    if fulltext:
        fulltext_section = f"""
## 全文（HTML版本）
{fulltext[:30000]}
"""
    else:
        fulltext_section = """
## 全文
（该论文暂无可解析的HTML版本，仅基于摘要分析）
"""

    return f"""你是一位资深AI研究员，请对以下论文进行深度精读和分析。

## 论文信息
- 标题: {metadata.get('title', '?')}
- 作者: {metadata.get('authors', '?')}
- 发表时间: {metadata.get('published', '?')}
- 分类: {metadata.get('category', '?')}
- arXiv: {metadata.get('arxiv_id', '?')}

## 摘要
{metadata.get('abstract', '')}

{fulltext_section}

请返回严格的 JSON 格式（不要 markdown 代码块包裹）：

{{
  "title_cn": "中文标题",
  "one_liner": "一句话总结（30字）",
  "research_question": "研究要解决什么问题（50字）",
  "background": "研究背景和动机（100字）",
  "method": {{
    "overview": "方法概述（100字）",
    "key_ideas": ["核心思想1", "核心思想2", "核心思想3"],
    "novelty": "创新点分析（80字）",
    "pipeline": ["步骤1: xxx", "步骤2: xxx", "步骤3: xxx"]
  }},
  "experiments": {{
    "setup": "实验设置（80字）",
    "datasets": ["数据集1", "数据集2"],
    "baselines": ["基线方法1", "基线方法2"],
    "key_results": ["关键结果1", "关键结果2", "关键结果3"],
    "ablation": "消融实验发现（50字，如无则写'无'）"
  }},
  "insights": ["洞察1", "洞察2", "洞察3"],
  "limitations": ["局限1", "局限2"],
  "impact": "对领域的影响（60字）",
  "who_should_read": ["适合阅读人群1", "适合阅读人群2"],
  "related_work": ["相关工作1", "相关工作2"],
  "code_available": "是否有代码发布（是/否/未知）",
  "score": {{
    "novelty": "1-5 创新性评分",
    "soundness": "1-5 实验严谨性评分",
    "impact": "1-5 影响力评分",
    "overall": "1-5 综合评分"
  }},
  "verdict": "综合评价（50字）"
}}"""


async def analyze_paper(url_or_id: str) -> Path | None:
    """
    深度精读一篇论文
    返回生成的报告文件路径
    """
    # 提取 arXiv ID
    arxiv_id = _extract_arxiv_id(url_or_id)
    if not arxiv_id:
        print(f"❌ 无法识别的 arXiv URL 或 ID: {url_or_id}")
        return None

    print(f"\n📖 论文精读: {arxiv_id}")
    print(f"   https://arxiv.org/abs/{arxiv_id}")
    print()

    # 1. 获取元数据
    print("[1/3] 获取论文信息...")
    metadata = await _fetch_arxiv_metadata(arxiv_id)
    if not metadata:
        print(f"  ❌ 无法获取论文元数据")
        return None

    print(f"  📄 {metadata['title'][:80]}...")
    print(f"  👤 {metadata['authors'][:100]}")

    # 2. 尝试获取全文
    print("[2/3] 尝试获取全文...")
    fulltext = await _fetch_html_fulltext(arxiv_id)
    if fulltext:
        print(f"  ✅ 获取HTML全文: {len(fulltext)} 字符")
    else:
        print(f"  ⚠️ 无HTML版本，基于摘要分析")

    # 3. AI 精读
    print("[3/3] DeepSeek 深度分析中...")
    prompt = _build_analysis_prompt(metadata, fulltext)
    estimated_tokens = len(prompt) // 3
    print(f"  📊 分析素材约 {estimated_tokens:,} tokens")

    response = _call_ai(prompt, max_tokens=6000)
    if not response:
        return None

    # 解析 JSON
    import json
    try:
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response[:-3]
        analysis = json.loads(response)
    except json.JSONDecodeError:
        print(f"  ⚠️ JSON解析失败，使用原文")
        analysis = {"raw_response": response}

    # 4. 生成报告
    report_path = _generate_report(metadata, analysis)
    print(f"\n  ✅ 精读报告: {report_path}")
    return report_path


def _score_bar(score) -> str:
    """数值转星标条"""
    try:
        s = int(score)
    except (TypeError, ValueError):
        s = 3
    return "★" * s + "☆" * (5 - s)


def _generate_report(metadata: dict, analysis: dict) -> Path:
    """生成论文精读 Markdown 报告"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    arxiv_id = metadata.get("arxiv_id", "unknown")
    clean_id = arxiv_id.split("v")[0]

    lines = []
    lines.append(f"# 📖 论文精读: {analysis.get('title_cn', metadata.get('title', '?'))}")
    lines.append("")
    lines.append(f"**原标题**: {metadata.get('title', '?')}")
    lines.append("")
    lines.append(f"**作者**: {metadata.get('authors', '?')}")
    lines.append(f"**发表时间**: {metadata.get('published', '?')} | **分类**: {metadata.get('category', '?')}")
    lines.append(f"📎 [arXiv](https://arxiv.org/abs/{clean_id}) | 📥 [PDF](https://arxiv.org/pdf/{clean_id})")
    lines.append(f"📅 分析日期: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    # 评分
    score = analysis.get("score", {})
    if score:
        lines.append("## 📊 评分")
        lines.append("")
        lines.append(f"| 维度 | 评分 |")
        lines.append(f"|------|------|")
        lines.append(f"| 创新性 | {_score_bar(score.get('novelty', 3))} |")
        lines.append(f"| 实验严谨性 | {_score_bar(score.get('soundness', 3))} |")
        lines.append(f"| 影响力 | {_score_bar(score.get('impact', 3))} |")
        lines.append(f"| **综合** | **{_score_bar(score.get('overall', 3))}** |")
        lines.append("")

    # 一句话总结
    if analysis.get("one_liner"):
        lines.append(f"> **{analysis['one_liner']}**")
        lines.append("")

    # 研究问题
    if analysis.get("research_question"):
        lines.append("## 🎯 研究问题")
        lines.append("")
        lines.append(analysis["research_question"])
        lines.append("")

    # 背景
    if analysis.get("background"):
        lines.append("## 📚 背景与动机")
        lines.append("")
        lines.append(analysis["background"])
        lines.append("")

    # 方法
    method = analysis.get("method", {})
    if method:
        lines.append("## 🔧 方法")
        lines.append("")
        if method.get("overview"):
            lines.append(method["overview"])
            lines.append("")

        key_ideas = method.get("key_ideas", [])
        if key_ideas:
            lines.append("### 核心思想")
            for idea in key_ideas:
                lines.append(f"- {idea}")
            lines.append("")

        if method.get("novelty"):
            lines.append(f"**创新点**: {method['novelty']}")
            lines.append("")

        pipeline = method.get("pipeline", [])
        if pipeline:
            lines.append("### 方法流程")
            for step in pipeline:
                lines.append(f"{step}")
            lines.append("")

    # 实验
    exp = analysis.get("experiments", {})
    if exp:
        lines.append("## 📈 实验")
        lines.append("")
        if exp.get("setup"):
            lines.append(f"**设置**: {exp['setup']}")
            lines.append("")

        datasets = exp.get("datasets", [])
        baselines = exp.get("baselines", [])
        if datasets or baselines:
            lines.append("| 数据集 | 基线方法 |")
            lines.append("|--------|----------|")
            max_len = max(len(datasets), len(baselines))
            for i in range(max_len):
                d = datasets[i] if i < len(datasets) else ""
                b = baselines[i] if i < len(baselines) else ""
                lines.append(f"| {d} | {b} |")
            lines.append("")

        key_results = exp.get("key_results", [])
        if key_results:
            lines.append("### 关键结果")
            for r in key_results:
                lines.append(f"- {r}")
            lines.append("")

        if exp.get("ablation") and exp["ablation"] != "无":
            lines.append(f"**消融实验**: {exp['ablation']}")
            lines.append("")

    # 洞察
    insights = analysis.get("insights", [])
    if insights:
        lines.append("## 💡 核心洞察")
        lines.append("")
        for i in insights:
            lines.append(f"- {i}")
        lines.append("")

    # 局限
    limitations = analysis.get("limitations", [])
    if limitations:
        lines.append("## ⚠️ 局限性")
        lines.append("")
        for l in limitations:
            lines.append(f"- {l}")
        lines.append("")

    # 影响
    if analysis.get("impact"):
        lines.append("## 🌍 领域影响")
        lines.append("")
        lines.append(analysis["impact"])
        lines.append("")

    # 相关工作和代码
    related = analysis.get("related_work", [])
    code = analysis.get("code_available", "未知")
    who = analysis.get("who_should_read", [])

    if related or code != "未知" or who:
        lines.append("## 📋 其他信息")
        lines.append("")

        if related:
            lines.append(f"**相关工作**: {' · '.join(related)}")
            lines.append("")
        if code != "未知":
            lines.append(f"**代码发布**: {code}")
            lines.append("")
        if who:
            lines.append(f"**适合阅读**: {' · '.join(who)}")
            lines.append("")

    # 综合评价
    if analysis.get("verdict"):
        lines.append("---")
        lines.append("")
        lines.append(f"> **综合评价**: {analysis['verdict']}")
        lines.append("")

    lines.append("---")
    lines.append(f"📬 由 AI信息助手 论文精读模块生成")

    file_path = OUTPUT_DIR / f"paper-{clean_id}-{datetime.now().strftime('%Y%m%d')}.md"
    file_path.write_text("\n".join(lines), encoding="utf-8")

    return file_path
