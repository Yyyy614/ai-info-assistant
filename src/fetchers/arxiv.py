"""
arXiv API 抓取器
- 官方API: http://export.arxiv.org/api/query
- 支持按类别、日期范围搜索
- 返回结构化论文信息
"""

import httpx
import feedparser
import asyncio
from datetime import datetime, timedelta
from storage import cache

ARXIV_API_URL = "https://export.arxiv.org/api/query"


def _build_query(categories: list[str], days_back: int, max_results: int) -> str:
    """构建 arXiv API 查询语句"""
    # 类别：cat:cs.AI OR cat:cs.CL ...
    cat_query = " OR ".join(f"cat:{c}" for c in categories)

    # 日期过滤（arXiv API 支持按日期搜但不是精确过滤，这里用 sortBy=submittedDate）
    return f"({cat_query})"


def _parse_entry(entry) -> dict:
    """解析单个论文条目"""
    # 提取 arxiv ID
    arxiv_id = entry.get("id", "").split("/abs/")[-1]
    # 去掉版本号
    arxiv_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id

    # 作者列表
    authors = ", ".join(a.get("name", "") for a in entry.get("authors", []))

    # 分类
    category = entry.get("arxiv_primary_category", {}).get("term", "")

    return {
        "arxiv_id": arxiv_id,
        "title": entry.get("title", "").strip().replace("\n", " "),
        "authors": authors,
        "abstract": entry.get("summary", "").strip().replace("\n", " "),
        "url": entry.get("link", ""),
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        "published_date": entry.get("published", "")[:10],
        "category": category,
        "source": "arxiv",
    }


async def fetch(categories: list[str], days_back: int = 1, max_results: int = 30) -> list[dict]:
    """
    抓取 arXiv 论文
    - categories: 类别列表，如 ["cs.AI", "cs.CL"]
    - days_back: 往回搜的天数
    - max_results: 最大返回数
    """
    query = _build_query(categories, days_back, max_results)
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(max_results),
    }

    # 用 params 构建缓存key
    cache_key = f"arxiv:{str(sorted(params.items()))}"
    cached = cache.get(cache_key, ttl=3600)  # arXiv 1小时缓存
    if cached:
        papers = cached.get("papers", [])
        print(f"  📄 arXiv: 从缓存读取 {len(papers)} 篇论文")
        return papers

    try:
        retries = 3
        resp = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=30, headers={
                    "User-Agent": "AI-Info-Assistant/1.0"
                }) as client:
                    resp = await client.get(ARXIV_API_URL, params=params)
                    if resp.status_code == 429:
                        if attempt < retries - 1:
                            wait = (attempt + 1) * 5
                            print(f"  ⏳ arXiv: 请求太频繁，等待 {wait}s 后重试...")
                            await asyncio.sleep(wait)
                            continue
                        else:
                            print(f"  ❌ arXiv: 重试{retries}次后仍被限速，请稍后再试")
                            return []
                    resp.raise_for_status()
                    break  # 成功，跳出循环
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < retries - 1:
                    continue
                raise

        if resp is None or resp.status_code != 200:
            print(f"  ❌ arXiv: 请求失败")
            return []

        feed = feedparser.parse(resp.text)
        papers = [_parse_entry(e) for e in feed.entries]

        # 写入缓存
        cache.set(cache_key, {"papers": papers})

        print(f"  📄 arXiv: 抓取到 {len(papers)} 篇论文")
        return papers

    except Exception as e:
        import traceback
        print(f"  ❌ arXiv: 抓取失败 - {type(e).__name__}: {e}")
        # 失败时不要缓存空结果，避免后续读取缓存
        return []
