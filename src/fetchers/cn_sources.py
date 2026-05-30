"""
国内AI资讯抓取器
- RSS 解析（机器之心、量子位等）
- 不需要 VPN
"""

import httpx
import feedparser
from storage import cache


CN_SOURCES = [
    {
        "name": "量子位",
        "rss": "https://www.qbitai.com/feed",
    },
    # 机器之心 RSS 已关闭（302到 /data-service 需登录），暂时移除
]


async def fetch(max_per_source: int = 10) -> list[dict]:
    """
    抓取国内AI资讯 RSS
    """
    all_articles = []

    for source in CN_SOURCES:
        name = source["name"]
        rss_url = source["rss"]

        cache_key = f"cn:{name}"
        cached = cache.get(cache_key, ttl=3600)
        if cached:
            articles = cached.get("articles", [])
            all_articles.extend(articles)
            continue

        try:
            async with httpx.AsyncClient(timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }) as client:
                resp = await client.get(rss_url)
                resp.raise_for_status()

            feed = feedparser.parse(resp.text)

            articles = []
            for entry in feed.entries[:max_per_source]:
                articles.append({
                    "url": entry.get("link", ""),
                    "title": entry.get("title", "").strip(),
                    "content": (entry.get("summary", "") or entry.get("description", ""))[:500],
                    "source": name,
                    "published_date": entry.get("published", "")[:10] or entry.get("updated", "")[:10],
                })

            cache.set(cache_key, {"articles": articles})
            all_articles.extend(articles)
            print(f"  🇨🇳 {name}: 抓取到 {len(articles)} 条资讯")

        except Exception as e:
            print(f"  ⚠️ {name}: RSS 抓取失败 - {e}")
            continue

    print(f"  🇨🇳 国内源: 共 {len(all_articles)} 条资讯")
    return all_articles
