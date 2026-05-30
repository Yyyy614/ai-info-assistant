"""
GitHub Trending 抓取器
- 通过 GitHub REST API 搜索热门AI项目
- 按 stars 排序
- 建议设置 GITHUB_TOKEN 环境变量提高速率限制
"""

import os
import httpx
from datetime import datetime, timedelta
from storage import cache

GITHUB_API = "https://api.github.com"


async def fetch_trending(
    languages: list[str],
    topics: list[str],
    max_repos: int = 15,
    days_back: int = 7,
    use_vpn: bool = False,
) -> list[dict]:
    """
    抓取 GitHub 热门AI项目
    搜索最近创建的AI相关仓库，按stars排序
    """
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # 使用 topics 搜索，比关键词搜索更精准
    topic_filters = " OR ".join(f"topic:{t}" for t in topics[:5])  # 限制 5 个 topic
    lang_filters = " OR ".join(f"language:{l}" for l in languages[:3])  # 限制 3 个语言

    # 简化的查询：话题过滤 + 日期
    query = f"{topic_filters} created:>={since_date}"
    # 确保查询不超过 GitHub 的 256 字符限制
    if len(query) > 250:
        query = query[:250]

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": str(min(max_repos, 30)),
    }

    cache_key = f"github:{hash(query)}"
    cached = cache.get(cache_key, ttl=7200)  # GitHub 2小时缓存
    if cached:
        repos = cached.get("repos", [])
        print(f"  🐙 GitHub: 从缓存读取 {len(repos)} 个项目")
        return repos

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-Info-Assistant/1.0",
    }

    # 如果有 GitHub token，可以提升速率限制
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{GITHUB_API}/search/repositories",
                params=params,
                headers=headers,
            )

            if resp.status_code == 403:
                if "rate limit" in resp.text.lower():
                    print("  ⚠️ GitHub: API速率限制，建议设置 GITHUB_TOKEN 或开启VPN")
                else:
                    print(f"  ⚠️ GitHub: 访问被拒绝 (403)")
                return []
            elif resp.status_code == 422:
                print(f"  ⚠️ GitHub: 查询格式错误 (422)，尝试简化查询")
                # 回退：只用 AI topic，不限定日期
                params["q"] = "topic:ai"
                resp = await client.get(
                    f"{GITHUB_API}/search/repositories",
                    params=params,
                    headers=headers,
                )

            resp.raise_for_status()
            data = resp.json()

        repos = []
        for item in data.get("items", []):
            repos.append({
                "repo_url": item.get("html_url", ""),
                "name": item.get("name", ""),
                "full_name": item.get("full_name", ""),
                "description": (item.get("description") or "")[:500],
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language", ""),
                "topics": ", ".join(item.get("topics", [])),
            })

        cache.set(cache_key, {"repos": repos})
        print(f"  🐙 GitHub: 抓取到 {len(repos)} 个项目")
        return repos

    except Exception as e:
        print(f"  ❌ GitHub: 抓取失败 - {e}")
        return []
