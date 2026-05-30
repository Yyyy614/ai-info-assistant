"""
Markdown 报告生成器
生成日报/周报的 Markdown 格式文件
"""

from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


def _importance_stars(score) -> str:
    """重要性评分转星标"""
    try:
        s = int(score)
    except (TypeError, ValueError):
        s = 3
    return "⭐" * min(s, 5)


def _tags_badges(tags: list[str]) -> str:
    """标签转 badges"""
    if not tags:
        return ""
    return " ".join(f"`{t}`" for t in tags[:4])


def generate_daily_report(
    papers: list[dict],
    repos: list[dict],
    articles: list[dict] | None = None,
) -> Path:
    """
    生成日报 Markdown 文件
    返回文件路径
    """
    today = datetime.now().strftime("%Y-%m-%d")
    today_cn = datetime.now().strftime("%Y年%m月%d日")

    lines = []
    lines.append(f"# 🧠 AI信息日报 | {today_cn}")
    lines.append("")
    lines.append(f"> 自动生成于 {datetime.now().strftime('%H:%M')} · 论文 {len(papers)} 篇 · 开源项目 {len(repos)} 个")
    lines.append("")

    # ====== 今日必读（论文 Top N） ======
    if papers:
        lines.append("---")
        lines.append("")
        lines.append("## 📄 最新论文")
        lines.append("")

        # 按 importance 排序
        sorted_papers = sorted(
            papers,
            key=lambda p: p.get("summary", {}).get("importance", 3),
            reverse=True,
        )

        for i, p in enumerate(sorted_papers, 1):
            s = p.get("summary", {})
            title = s.get("title_cn") or p.get("title", "?")
            one_liner = s.get("one_liner", "")
            key_method = s.get("key_method", "")
            tags = s.get("tags", [])
            importance = s.get("importance", 3)
            arxiv_id = p.get("arxiv_id", "")
            authors = p.get("authors", "")
            url = p.get("url", "")
            pdf_url = p.get("pdf_url", "")
            category = p.get("category", "")

            lines.append(f"### {i}. {title}")
            lines.append("")
            lines.append(f"{_importance_stars(importance)} {_tags_badges(tags)} | 📂 {category}")
            lines.append("")
            if one_liner:
                lines.append(f"> **{one_liner}**")
                lines.append("")
            if key_method:
                lines.append(f"**关键方法**: {key_method}")
                lines.append("")
            lines.append(f"- 作者: {authors[:150]}")
            lines.append(f"- 📎 [论文]({url}) | 📥 [PDF]({pdf_url})")
            lines.append("")

    # ====== 开源项目 ======
    if repos:
        lines.append("---")
        lines.append("")
        lines.append("## 🛠️ 值得关注的开源项目")
        lines.append("")

        sorted_repos = sorted(repos, key=lambda r: r.get("stars", 0), reverse=True)

        for i, r in enumerate(sorted_repos, 1):
            s = r.get("summary", {})
            name = r.get("name", "?")
            name_cn = s.get("name_cn", name)
            one_liner = s.get("one_liner", "")
            why_matters = s.get("why_matters", "")
            tags = s.get("tags", [])
            difficulty = s.get("difficulty", "")
            stars = r.get("stars", 0)
            language = r.get("language", "")
            repo_url = r.get("repo_url", "")
            full_name = r.get("full_name", "")

            lines.append(f"### {i}. {name_cn}")
            lines.append("")
            lines.append(f"⭐ {stars:,} | 🔧 {language} | {_tags_badges(tags)}")
            if difficulty:
                lines[-1] += f" | 📊 {difficulty}"
            lines.append("")
            if one_liner:
                lines.append(f"> **{one_liner}**")
                lines.append("")
            if why_matters:
                lines.append(f"**为什么值得关注**: {why_matters}")
                lines.append("")
            lines.append(f"- 📂 [{full_name}]({repo_url})")
            lines.append("")

    # ====== 国内资讯 ======
    if articles:
        lines.append("---")
        lines.append("")
        lines.append("## 🇨🇳 国内资讯")
        lines.append("")
        for i, a in enumerate(articles, 1):
            lines.append(f"{i}. [{a.get('title', '?')}]({a.get('url', '#')}) — {a.get('source', '')}")
        lines.append("")

    # ====== 页脚 ======
    lines.append("---")
    lines.append("")
    lines.append(f"📬 由 AI信息助手 自动生成 · [GitHub](https://github.com/Yyyy614/ai-info-assistant)")
    lines.append("")

    # 写出文件
    daily_dir = OUTPUT_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    file_path = daily_dir / f"report-{today}.md"
    file_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"  📝 日报已生成: {file_path}")
    return file_path
