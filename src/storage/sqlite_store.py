"""
SQLite 存储层
- 存储抓取的论文、项目、文章
- 基于URL去重（INSERT OR IGNORE）
- 查询历史记录
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "assistant.db"


def get_db_path():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return str(DB_PATH)


def init_db():
    """初始化数据库，创建所有表"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 论文表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_id TEXT UNIQUE,
            title TEXT NOT NULL,
            authors TEXT,
            abstract TEXT,
            url TEXT UNIQUE NOT NULL,
            pdf_url TEXT,
            published_date TEXT,
            category TEXT,
            source TEXT DEFAULT 'arxiv',
            summary_cn TEXT,
            fetched_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # 开源项目表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_url TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            full_name TEXT,
            description TEXT,
            stars INTEGER DEFAULT 0,
            language TEXT,
            topics TEXT,
            readme_cn TEXT,
            fetched_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # 文章/动态表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            source TEXT,
            published_date TEXT,
            summary_cn TEXT,
            fetched_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # 报告表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            report_date TEXT NOT NULL,
            file_path TEXT NOT NULL,
            item_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.commit()
    conn.close()


def save_papers(papers: list[dict]) -> int:
    """保存论文，返回新增数量"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    new_count = 0

    for p in papers:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO papers (arxiv_id, title, authors, abstract, url, pdf_url, published_date, category, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p.get("arxiv_id"),
                p.get("title"),
                p.get("authors"),
                p.get("abstract"),
                p.get("url"),
                p.get("pdf_url"),
                p.get("published_date"),
                p.get("category"),
                p.get("source", "arxiv"),
            ))
            if cursor.rowcount > 0:
                new_count += 1
        except Exception as e:
            print(f"  [存储错误] 论文 '{p.get('title', '?')[:40]}': {e}")

    conn.commit()
    conn.close()
    return new_count


def save_repos(repos: list[dict]) -> int:
    """保存开源项目，返回新增数量"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    new_count = 0

    for r in repos:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO repos (repo_url, name, full_name, description, stars, language, topics)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get("repo_url"),
                r.get("name"),
                r.get("full_name"),
                r.get("description"),
                r.get("stars", 0),
                r.get("language"),
                r.get("topics"),
            ))
            if cursor.rowcount > 0:
                new_count += 1
        except Exception as e:
            print(f"  [存储错误] 项目 '{r.get('name', '?')}': {e}")

    conn.commit()
    conn.close()
    return new_count


def save_articles(articles: list[dict]) -> int:
    """保存文章，返回新增数量"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    new_count = 0

    for a in articles:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO articles (url, title, content, source, published_date)
                VALUES (?, ?, ?, ?, ?)
            """, (
                a.get("url"),
                a.get("title"),
                a.get("content"),
                a.get("source"),
                a.get("published_date"),
            ))
            if cursor.rowcount > 0:
                new_count += 1
        except Exception as e:
            print(f"  [存储错误] 文章 '{a.get('title', '?')[:40]}': {e}")

    conn.commit()
    conn.close()
    return new_count


def get_today_papers() -> list[dict]:
    """获取今天抓取的所有论文"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT * FROM papers WHERE date(fetched_at) = ? ORDER BY id DESC
    """, (today,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_repos() -> list[dict]:
    """获取今天抓取的所有项目"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT * FROM repos WHERE date(fetched_at) = ? ORDER BY stars DESC
    """, (today,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_paper_summary(paper_id: int, summary_cn: str):
    """更新论文的中文摘要"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE papers SET summary_cn = ? WHERE id = ?", (summary_cn, paper_id))
    conn.commit()
    conn.close()


def save_report(report_type: str, report_date: str, file_path: str, item_count: int):
    """记录生成的报告"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reports (report_type, report_date, file_path, item_count)
        VALUES (?, ?, ?, ?)
    """, (report_type, report_date, file_path, item_count))
    conn.commit()
    conn.close()
