# backend/services/market_cache.py
# ==============================
# 单标的基础原始行情运行时缓存
#
# 职责：
#   - 缓存原始 1d / 1m / 5m 数据
#   - 管理 last_access_at
#   - 管理超时释放
#   - 支持按 market+code+freq 释放
#
# 设计原则：
#   - 只缓存基础原始真相源
#   - 不缓存复权成品
#   - 不缓存重采样成品
#   - 释放规则：
#       * 1m  未访问超过 1 分钟释放
#       * 5m  未访问超过 5 分钟释放
#       * 1d  未访问超过 5 分钟释放
# ==============================

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Optional
from datetime import datetime
import threading
import pandas as pd


@dataclass
class CacheItem:
    market: str
    code: str
    base_freq: str
    df: pd.DataFrame
    last_access_at: datetime


class MarketCache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: Dict[Tuple[str, str, str], CacheItem] = {}

    def _key(self, market: str, code: str, base_freq: str) -> Tuple[str, str, str]:
        return (
            str(market or "").strip().upper(),
            str(code or "").strip(),
            str(base_freq or "").strip(),
        )

    def _expire_seconds(self, base_freq: str) -> int:
        f = str(base_freq or "").strip()
        if f == "1m":
            return 60
        if f in ("5m", "1d"):
            return 300
        return 300

    def _purge_expired_locked(self) -> None:
        now = datetime.now()
        to_delete = []

        for k, item in self._items.items():
            expire = self._expire_seconds(item.base_freq)
            if (now - item.last_access_at).total_seconds() > expire:
                to_delete.append(k)

        for k in to_delete:
            self._items.pop(k, None)

    def get(self, market: str, code: str, base_freq: str) -> Optional[pd.DataFrame]:
        with self._lock:
            self._purge_expired_locked()
            k = self._key(market, code, base_freq)
            item = self._items.get(k)
            if not item:
                return None
            item.last_access_at = datetime.now()
            return item.df.copy()

    def put(self, market: str, code: str, base_freq: str, df: pd.DataFrame) -> None:
        with self._lock:
            self._purge_expired_locked()
            k = self._key(market, code, base_freq)
            self._items[k] = CacheItem(
                market=str(market).strip().upper(),
                code=str(code).strip(),
                base_freq=str(base_freq).strip(),
                df=df.copy(),
                last_access_at=datetime.now(),
            )

    def release(self, market: str, code: str, request_freq: str) -> bool:
        """
        按请求频率语义释放真实基础缓存。
        """
        base_freq = self._request_freq_to_base_freq(request_freq)
        with self._lock:
            self._purge_expired_locked()
            k = self._key(market, code, base_freq)
            existed = k in self._items
            self._items.pop(k, None)
            return existed

    def _request_freq_to_base_freq(self, request_freq: str) -> str:
        f = str(request_freq or "").strip()
        if f == "1m":
            return "1m"
        if f in ("5m", "15m", "30m", "60m"):
            return "5m"
        if f in ("1d", "1w", "1M"):
            return "1d"
        return f

    def size(self) -> int:
        with self._lock:
            self._purge_expired_locked()
            return len(self._items)


_CACHE: Optional[MarketCache] = None


def get_market_cache() -> MarketCache:
    global _CACHE
    if _CACHE is None:
        _CACHE = MarketCache()
    return _CACHE
