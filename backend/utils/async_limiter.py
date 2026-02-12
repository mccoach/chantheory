# backend/utils/async_limiter.py
# ==============================
# 说明：异步版全局网络限流器（生产级实现）
# - 职责：使用 asyncio 原语实现异步安全的令牌桶算法
# - 本次改动：
#     1) 保留全局限流（总闸门）
#     2) 新增分源限流（新浪/东财/baostock），在全局限流基础上再限一次
# ==============================

from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import Callable, Any, Awaitable, Optional, Dict

from backend.settings import settings
from backend.utils.logger import get_logger

_LOG = get_logger("async_limiter")


class AsyncTokenBucket:
    """
    异步版令牌桶限流器（生产级实现）。

    核心设计：
    - 使用 asyncio.Lock 保护令牌数量的修改
    - 使用 asyncio.Condition 实现高效的等待机制
    - 在等待时会释放锁，不会阻塞其他协程
    """

    def __init__(self, rate: float, capacity: int):
        """
        初始化令牌桶。

        Args:
            rate: 每秒生成的令牌数（如 2.0 表示每秒2个请求）
            capacity: 桶的最大容量（也即“最大突发令牌数”）
        """
        self.rate = max(0.0001, float(rate))
        self.capacity = max(1, int(capacity))

        self._tokens = float(self.capacity)
        self._last_refill = time.time()

        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)

    async def acquire(self, tokens: int = 1):
        """
        异步获取指定数量的令牌。

        如果当前令牌不足，会等待直到有足够的令牌。
        """
        need = max(1, int(tokens))
        async with self._condition:
            while True:
                now = time.time()
                elapsed = now - self._last_refill
                if elapsed > 0:
                    new_tokens = elapsed * self.rate
                    self._tokens = min(self.capacity, self._tokens + new_tokens)
                    self._last_refill = now

                if self._tokens >= need:
                    self._tokens -= need
                    return

                tokens_needed = need - self._tokens
                wait_time = tokens_needed / self.rate if self.rate > 0 else 1.0

                try:
                    await asyncio.wait_for(asyncio.sleep(wait_time), timeout=wait_time + 1.0)
                except asyncio.TimeoutError:
                    pass


_global_async_bucket: Optional[AsyncTokenBucket] = None
_bucket_init_lock = asyncio.Lock()

_provider_buckets: Dict[str, AsyncTokenBucket] = {}
_provider_lock = asyncio.Lock()


async def get_global_async_bucket() -> AsyncTokenBucket:
    """
    获取全局异步令牌桶单例。
    """
    global _global_async_bucket

    if _global_async_bucket is None:
        async with _bucket_init_lock:
            if _global_async_bucket is None:
                _global_async_bucket = AsyncTokenBucket(
                    rate=float(settings.network_requests_per_second),
                    capacity=int(settings.network_max_burst_tokens),
                )

                _LOG.info(
                    "Async token bucket initialized: rate=%s/s, capacity=%s",
                    settings.network_requests_per_second,
                    settings.network_max_burst_tokens,
                )

    return _global_async_bucket


async def get_provider_bucket(provider: str) -> Optional[AsyncTokenBucket]:
    """
    获取某个 provider 的分源令牌桶（可选）。

    若 settings.provider_limiters 未配置该 provider，则返回 None（表示不额外限）。
    """
    p = (provider or "").strip().lower()
    if not p:
        return None

    cfg = (settings.provider_limiters or {}).get(p)
    if not isinstance(cfg, dict) or not cfg:
        return None

    async with _provider_lock:
        bucket = _provider_buckets.get(p)
        if bucket is None:
            rps = float(cfg.get("rps", settings.network_requests_per_second))
            burst = int(cfg.get("burst", settings.network_max_burst_tokens))
            bucket = AsyncTokenBucket(rate=rps, capacity=burst)
            _provider_buckets[p] = bucket
            _LOG.info(
                "Provider token bucket initialized: provider=%s rate=%s/s capacity=%s",
                p, rps, burst
            )
        return bucket


def limit_async_network_io(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """
    全局网络IO限流装饰器（保持兼容：已有代码全部继续可用）。
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not bool(getattr(settings, "network_limiter_enabled", True)):
            return await func(*args, **kwargs)

        bucket = await get_global_async_bucket()
        await bucket.acquire(1)
        return await func(*args, **kwargs)

    return wrapper


def limit_provider_network_io(provider: str) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """
    分源+全局 两级限流装饰器。

    行为：
      - 若启用限流：
          1) 若 provider 配置存在：先过 provider 桶
          2) 再过全局桶
      - 若未启用限流：直接执行
    """
    prov = (provider or "").strip().lower()

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not bool(getattr(settings, "network_limiter_enabled", True)):
                return await func(*args, **kwargs)

            pb = await get_provider_bucket(prov)
            if pb is not None:
                await pb.acquire(1)

            gb = await get_global_async_bucket()
            await gb.acquire(1)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class TaskContext:
    """
    任务优先级上下文管理器（占位符）。
    """
    def __init__(self, priority: int = 100):
        self.priority = priority

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
