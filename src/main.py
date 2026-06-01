"""
AI信息助手 - 主入口
用法：
  python main.py daily              # 生成日报
  python main.py weekly             # 生成周报
  python main.py schedule           # 启动定时任务
  python main.py config             # 查看当前配置
"""

import sys
import asyncio
import yaml
from pathlib import Path
from datetime import datetime

# Windows 终端 UTF-8 支持
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).parent))
from storage import sqlite_store
from fetchers import arxiv, github, hackernews, paperswithcode, cn_sources
from processor import summarizer
from reporter import markdown_reporter
from deepdive import repo_analyzer, paper_digger


def load_config() -> dict:
    """加载配置文件"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        print(f"⚠️ 配置文件不存在: {config_path}")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def fetch_all(config: dict, use_vpn: bool = False):
    """并发抓取所有数据源"""
    sources = config.get("sources", {})

    tasks = []
    task_names = []

    # arXiv
    if sources.get("arxiv", {}).get("enabled", True):
        arxiv_cfg = sources["arxiv"]
        tasks.append(arxiv.fetch(
            categories=arxiv_cfg.get("categories", ["cs.AI"]),
            days_back=arxiv_cfg.get("days_back", 1),
            max_results=arxiv_cfg.get("max_results", 30),
        ))
        task_names.append("arxiv")

    # GitHub
    if sources.get("github", {}).get("enabled", True):
        gh_cfg = sources["github"]
        tasks.append(github.fetch_trending(
            languages=gh_cfg.get("languages", ["python"]),
            topics=gh_cfg.get("topics", []),
            max_repos=gh_cfg.get("max_repos", 15),
            use_vpn=use_vpn,
        ))
        task_names.append("github")

    # Hacker News
    if sources.get("hackernews", {}).get("enabled", True):
        hn_cfg = sources["hackernews"]
        tasks.append(hackernews.fetch(
            keywords=hn_cfg.get("keywords", ["AI", "LLM"]),
            max_posts=hn_cfg.get("max_posts", 20),
        ))
        task_names.append("hackernews")

    # Papers With Code
    if sources.get("paperswithcode", {}).get("enabled", True):
        pwc_cfg = sources["paperswithcode"]
        tasks.append(paperswithcode.fetch(
            max_results=pwc_cfg.get("max_results", 15),
        ))
        task_names.append("paperswithcode")

    # 国内源
    if sources.get("cn_sources", {}).get("enabled", True):
        tasks.append(cn_sources.fetch())
        task_names.append("cn_sources")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    papers = []
    repos = []
    articles = []

    for name, r in zip(task_names, results):
        if isinstance(r, Exception):
            print(f"  ⚠️ {name} 抓取异常: {r}")
            continue
        if not r or not isinstance(r, list):
            continue

        if name in ("arxiv", "paperswithcode"):
            papers.extend(r)
        elif name == "github":
            repos.extend(r)
        elif name in ("hackernews", "cn_sources"):
            articles.extend(r)

    return papers, repos, articles


async def run_daily(config: dict):
    """执行日报生成流程"""
    print("=" * 50)
    print(f"  🧠 AI信息助手 - 日报生成")
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print()

    # 1. 初始化数据库
    print("[1/5] 初始化数据库...")
    sqlite_store.init_db()

    # 2. 抓取数据
    print("[2/5] 正在抓取最新数据...")
    papers, repos, articles = await fetch_all(config)

    if not papers and not repos and not articles:
        print("  ⚠️ 未抓取到任何数据，请检查网络或配置")
        return

    # 3. 存储（自动去重）
    print("[3/5] 存储数据并去重...")
    new_papers = sqlite_store.save_papers(papers)
    new_repos = sqlite_store.save_repos(repos)
    new_articles = sqlite_store.save_articles(articles)
    print(f"  📊 新增论文: {new_papers}/{len(papers)} | 新项目: {new_repos}/{len(repos)} | 新资讯: {new_articles}/{len(articles)}")

    # 4. AI 翻译+摘要（仅处理论文和项目）
    print("[4/5] AI翻译总结中...")
    summarized_papers = summarizer.summarize_papers(papers) if papers else []
    summarized_repos = summarizer.summarize_repos(repos) if repos else []

    # 更新数据库中的中文摘要
    for p in summarized_papers:
        s = p.get("summary", {})
        summary_text = f"{s.get('title_cn', '')} | {s.get('one_liner', '')} | {s.get('key_method', '')}"
        try:
            arxiv_id = p.get("arxiv_id", "")
            import sqlite3
            conn = sqlite3.connect(sqlite_store.get_db_path())
            conn.execute(
                "UPDATE papers SET summary_cn = ? WHERE arxiv_id = ?",
                (summary_text, arxiv_id),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    # 5. 生成报告
    print("[5/5] 生成报告...")
    report_path = markdown_reporter.generate_daily_report(
        papers=summarized_papers,
        repos=summarized_repos,
        articles=articles,
    )

    # 记录报告
    sqlite_store.save_report(
        report_type="daily",
        report_date=datetime.now().strftime("%Y-%m-%d"),
        file_path=str(report_path),
        item_count=len(summarized_papers) + len(summarized_repos) + len(articles),
    )

    print()
    print("=" * 50)
    print(f"  ✅ 完成！报告: {report_path}")
    print("=" * 50)


async def run_weekly(config: dict):
    """执行周报生成流程（逻辑同日报，但数据范围更大）"""
    print("=" * 50)
    print(f"  🧠 AI信息助手 - 周报生成")
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print()

    sqlite_store.init_db()

    # 周报：扩大抓取范围
    config_weekly = config.copy()
    if "sources" in config_weekly:
        arxiv_cfg = config_weekly["sources"].get("arxiv", {})
        arxiv_cfg["days_back"] = 7
        arxiv_cfg["max_results"] = 60
        config_weekly["sources"]["arxiv"] = arxiv_cfg

        gh_cfg = config_weekly["sources"].get("github", {})
        gh_cfg["max_repos"] = 30
        config_weekly["sources"]["github"] = gh_cfg

    print("[1/4] 抓取最近7天数据...")
    papers, repos, articles = await fetch_all(config_weekly)

    print("[2/4] 存储去重...")
    sqlite_store.save_papers(papers)
    sqlite_store.save_repos(repos)
    sqlite_store.save_articles(articles)

    print("[3/4] AI翻译总结...")
    summarized_papers = summarizer.summarize_papers(papers)
    summarized_repos = summarizer.summarize_repos(repos)

    print("[4/4] 生成周报...")
    report_path = markdown_reporter.generate_daily_report(
        papers=summarized_papers,
        repos=summarized_repos,
        articles=articles,
    )

    # 移动到 weekly 目录
    import shutil
    weekly_dir = Path(markdown_reporter.OUTPUT_DIR) / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_path = weekly_dir / f"weekly-{datetime.now().strftime('%Y-%m-%d')}.md"
    shutil.move(str(report_path), str(weekly_path))

    print()
    print(f"  ✅ 周报已生成: {weekly_path}")


def run_schedule(config: dict, mode: str = "weekly"):
    """启动定时任务
    mode: daily(工作日早9点日报) / weekly(每周一早9点周报)
    """
    try:
        import schedule
        import time as time_module
    except ImportError:
        print("⚠️ 请先安装 schedule: pip install schedule")
        return

    if mode == "daily":
        async def job_async():
            await run_daily(config)
        def job():
            asyncio.run(job_async())
        schedule.every().monday.at("09:00").do(job)
        schedule.every().tuesday.at("09:00").do(job)
        schedule.every().wednesday.at("09:00").do(job)
        schedule.every().thursday.at("09:00").do(job)
        schedule.every().friday.at("09:00").do(job)
        print("⏰ 定时任务已启动：工作日 09:00 自动生成日报")
    else:
        async def job_async():
            await run_weekly(config)
        def job():
            asyncio.run(job_async())
        schedule.every().monday.at("09:00").do(job)
        print("⏰ 定时任务已启动：每周一 09:00 自动生成周报（回顾上周）")

    print("   按 Ctrl+C 停止")
    print()

    # 先跑一次
    print("📋 立即执行一次...")
    job()

    while True:
        schedule.run_pending()
        time_module.sleep(60)


def show_config(config: dict):
    """显示当前配置摘要"""
    print("=" * 40)
    print("  📋 当前配置")
    print("=" * 40)
    print()

    sources = config.get("sources", {})
    for name, cfg in sources.items():
        enabled = "✅" if cfg.get("enabled", True) else "❌"
        print(f"  {enabled} {name}")
        if enabled == "❌" and name in ("twitter", "scholar"):
            print(f"       ⚠️ 需要VPN，开启请修改 config.yaml")

    print()
    report = config.get("report", {})
    print(f"  📝 日报: Top {report.get('daily', {}).get('top_n', 10)}")
    print(f"  📝 周报: Top {report.get('weekly', {}).get('top_n', 20)}")
    print()


# ====== CLI ======

def main():
    if len(sys.argv) < 2:
        print("AI信息助手 - 用法:")
        print("  python main.py daily              生成日报")
        print("  python main.py weekly             生成周报")
        print("  python main.py deepdive --repo <url>  深度分析开源项目")
        print("  python main.py schedule           启动定时任务（工作日早9点）")
        print("  python main.py config             查看当前配置")
        return

    command = sys.argv[1]
    config = load_config()

    if command == "daily":
        asyncio.run(run_daily(config))
    elif command == "weekly":
        asyncio.run(run_weekly(config))
    elif command == "deepdive":
        # 解析参数
        repo_url = None
        paper_url = None
        for i, arg in enumerate(sys.argv):
            if arg == "--repo" and i + 1 < len(sys.argv):
                repo_url = sys.argv[i + 1]
            elif arg == "--paper" and i + 1 < len(sys.argv):
                paper_url = sys.argv[i + 1]

        if repo_url:
            asyncio.run(repo_analyzer.analyze_repo(repo_url))
        elif paper_url:
            asyncio.run(paper_digger.analyze_paper(paper_url))
        else:
            print("❌ 请指定分析目标:")
            print("  python main.py deepdive --repo https://github.com/xxx/yyy")
            print("  python main.py deepdive --paper https://arxiv.org/abs/XXXX.XXXXX")
    elif command == "schedule":
        mode = "weekly"  # 默认周报
        for i, arg in enumerate(sys.argv):
            if arg == "--mode" and i + 1 < len(sys.argv):
                mode = sys.argv[i + 1]
        run_schedule(config, mode)
    elif command == "config":
        show_config(config)
    else:
        print(f"❌ 未知命令: {command}")
        print("可用: daily, weekly, deepdive, schedule, config")


if __name__ == "__main__":
    main()
