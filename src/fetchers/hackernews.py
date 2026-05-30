"""
Hacker News 抓取器
- 通过 Algolia API 搜索 AI 相关热门帖子和讨论
- 免费，无需认证，不需要 VPN
"""

import asyncio
import httpx
from datetime import datetime, timedelta
from storage import cache

ALGOLIA_API = "https://hn.algolia.com/api/v1"


async def fetch(
    keywords: list[str],
    max_posts: int = 20,
    days_back: int = 3,
) -> list[dict]:
    """
    搜索 HN 上与 AI 相关的热门帖子
    按点赞数 + 评论数排序
    """
    all_posts = []

    # Algolia 不支持 OR 查询，逐个关键词搜索
    for keyword in keywords[:6]:  # 限制6个关键词避免太多请求
        cache_key = f"hn:{keyword}:{days_back}"
        cached = cache.get(cache_key, ttl=3600)
        if cached:
            posts = cached.get("posts", [])
            all_posts.extend(posts)
            continue

        try:
            # 用最近 N 天的数值时间戳过滤
            since_ts = int((datetime.now() - timedelta(days=days_back)).timestamp())

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{ALGOLIA_API}/search_by_date",
                    params={
                        "query": keyword,
                        "tags": "story",
                        "hitsPerPage": str(min(max_posts // len(keywords) + 3, 15)),
                        "numericFilters": f"created_at_i>{since_ts}",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            posts = []
            for item in data.get("hits", []):
                posts.append({
                    "url": item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}",
                    "title": item.get("title", ""),
                    "content": item.get("story_text") or "",
                    "source": "HackerNews",
                    "published_date": item.get("created_at", "")[:10],
                    "points": item.get("points", 0),
                    "num_comments": item.get("num_comments", 0),
                })

            cache.set(cache_key, {"posts": posts})
            all_posts.extend(posts)

            # Algolia 有速率限制，加个间隔
            await asyncio.sleep(0.5)

        except Exception as e:
            print(f"  ⚠️ HackerNews: '{keyword}' 抓取失败 - {e}")
            continue

    # 去重 + 按热度排序
    seen = set()
    unique = []
    for p in all_posts:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)

    unique.sort(key=lambda p: p.get("points", 0) + p.get("num_comments", 0) * 2, reverse=True)
    unique = unique[:max_posts]

    print(f"  🗞️  HackerNews: 抓取到 {len(unique)} 条AI相关帖子")
    return unique
