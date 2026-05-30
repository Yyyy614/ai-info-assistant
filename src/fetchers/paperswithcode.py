"""
Papers With Code / HuggingFace Papers 抓取器
- PWC API 已迁至 HuggingFace
- 获取每日/每周趋势论文
"""

import httpx
from storage import cache

HF_API = "https://huggingface.co/api"


async def fetch(max_results: int = 15) -> list[dict]:
    """
    抓取 HuggingFace 上的趋势论文
    """
    cache_key = f"hf:papers:{max_results}"
    cached = cache.get(cache_key, ttl=7200)
    if cached:
        papers = cached.get("papers", [])
        print(f"  📊 HF Papers: 从缓存读取 {len(papers)} 篇")
        return papers

    papers = []

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # HuggingFace daily papers API
            resp = await client.get(
                f"{HF_API}/daily_papers",
                params={"limit": str(min(max_results, 20))},
            )
            resp.raise_for_status()
            data = resp.json()

        for item in data[:max_results]:
            paper = item.get("paper", {})
            papers.append({
                "title": paper.get("title", ""),
                "url": f"https://huggingface.co/papers/{paper.get('id', '')}",
                "arxiv_id": paper.get("arxivId", ""),
                "authors": "",  # HF daily papers 不直接包含作者
                "abstract": (paper.get("summary") or "")[:1000],
                "published_date": paper.get("publishedAt", "")[:10] or paper.get("upvote", ""),
                "category": "huggingface",
                "source": "huggingface",
                "code_url": "",  # HF papers 可能包含代码链接
            })

        cache.set(cache_key, {"papers": papers})
        print(f"  📊 HF Papers: 抓取到 {len(papers)} 篇趋势论文")
        return papers

    except httpx.ConnectTimeout:
        print(f"  ⚠️ HF Papers: 连接超时，可能需要开启VPN访问 huggingface.co")
        return []
    except httpx.ConnectError:
        print(f"  ⚠️ HF Papers: 无法连接 huggingface.co，可能需要开启VPN")
        return []
    except Exception as e:
        print(f"  ❌ HF Papers: 抓取失败 - {e}")
        return []
