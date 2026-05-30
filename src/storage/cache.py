"""
简单的请求缓存
- 基于文件缓存，避免短时间内重复请求同一URL
- 默认缓存1小时
"""

import json
import time
import hashlib
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
CACHE_TTL = 3600  # 默认1小时


def _get_cache_path(url: str) -> Path:
    """根据URL生成缓存文件路径"""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{url_hash}.json"


def get(url: str, ttl: int = CACHE_TTL) -> dict | None:
    """
    从缓存读取数据
    返回 None 表示缓存不存在或已过期
    """
    cache_path = _get_cache_path(url)
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if time.time() - data["_cached_at"] > ttl:
            return None  # 过期
        return data["_payload"]
    except (json.JSONDecodeError, KeyError):
        return None


def set(url: str, payload: dict):
    """写入缓存"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _get_cache_path(url)
    data = {
        "_cached_at": time.time(),
        "_url": url,
        "_payload": payload,
    }
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear():
    """清空所有缓存"""
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
