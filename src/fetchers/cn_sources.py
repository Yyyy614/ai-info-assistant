"""
国内AI资讯抓取器
- RSS 解析（机器之心、量子位等）
- 不需要 VPN
- 数据源列表从 config.yaml 读取，config 即唯一事实来源
"""

import httpx
import feedparser
from pathlib import Path
import yaml
from storage import cache


def _load_sources() -> list[dict]:
    """从 config.yaml 读取国内数据源配置，读取失败时使用兜底默认源"""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    try:
        if not config_path.exists():
            raise FileNotFoundError("config.yaml not found")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        sources = config.get("sources", {}).get("cn_sources", {}).get("sources", [])
        if not sources:
            raise ValueError("config.yaml 中 cn_sources.sources 为空")
        return sources
    except Exception as e:
        print(f"  ⚠️ 读取 cn_sources 配置失败 ({e})，使用兜底默认源")
        return [
            {"name": "量子位", "rss": "https://www.qbitai.com/feed"},
        ]


async def fetch(max_per_source: int = 10) -> list[dict]:
    """
    抓取国内AI资讯 RSS
    """
    sources = _load_sources()
    all_articles = []

    for source in sources:
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
