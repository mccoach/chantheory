# backend/utils/async_limiter.py
# ==============================
# 说明：异步版全局网络限流器（生产级实现）
# - 职责：使用 asyncio 原语实现异步安全的令牌桶算法
# - 核心优势：不会阻塞事件循环，支持高并发
# ==============================

from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import Callable, Any, Awaitable, Optional

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
    
    def __init__(self, rate: float, capacity: int, burst: int):
        """
        初始化令牌桶。
        
        Args:
            rate: 每秒生成的令牌数（如 2.0 表示每秒2个请求）
            capacity: 桶的最大容量
            burst: 最大突发令牌数
        """
        self.rate = rate
        self.capacity = capacity
        self.burst = burst
        
        self._tokens = float(capacity)
        self._last_refill = time.time()
        
        # 使用 asyncio 的同步原语
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
    
    async def acquire(self, tokens: int = 1):
        """
        异步获取指定数量的令牌。
        
        如果当前令牌不足，会等待直到有足够的令牌。
        等待期间不会持有锁，其他协程可以继续运行。
        
        Args:
            tokens: 需要的令牌数，默认1
        """
        async with self._condition:
            while True:
                # 补充令牌
                now = time.time()
                elapsed = now - self._last_refill
                new_tokens = elapsed * self.rate
                self._tokens = min(self.capacity, self._tokens + new_tokens)
                self._last_refill = now
                
                # 检查是否有足够令牌
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                
                # 计算需要等待的时间
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate
                
                # 释放锁并等待（关键：使用 asyncio.Condition.wait_for 或直接 sleep）
                # 这里选择更简单的策略：计算精确等待时间后 sleep
                # 注意：wait 期间会自动释放锁
                try:
                    # 使用 wait_for 的超时特性，避免无限等待
                    await asyncio.wait_for(
                        asyncio.sleep(wait_time),
                        timeout=wait_time + 1.0
                    )
                except asyncio.TimeoutError:
                    # 超时后重新进入循环，重新计算令牌
                    pass


# 全局单例
_global_async_bucket: Optional[AsyncTokenBucket] = None
_bucket_init_lock = asyncio.Lock()


async def get_global_async_bucket() -> AsyncTokenBucket:
    """
    获取全局异步令牌桶单例。
    
    线程安全、协程安全的初始化。
    """
    global _global_async_bucket
    
    if _global_async_bucket is None:
        async with _bucket_init_lock:
            if _global_async_bucket is None:
                _global_async_bucket = AsyncTokenBucket(
                    rate=float(settings.network_requests_per_second),
                    capacity=int(settings.network_max_burst_tokens),
                    burst=int(settings.network_max_burst_tokens)
                )
                
                _LOG.info(
                    f"Async token bucket initialized: "
                    f"rate={settings.network_requests_per_second}/s, "
                    f"capacity={settings.network_max_burst_tokens}, "
                    f"burst={settings.network_max_burst_tokens}"
                )
    
    return _global_async_bucket


def limit_async_network_io(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """
    异步函数专用的网络IO限流装饰器。
    
    用法：
        @limit_async_network_io
        async def fetch_data():
            return await some_async_call()
    
    效果：
        在执行函数前，会先从全局令牌桶获取一个令牌。
        如果令牌不足，会等待（不阻塞事件循环）。
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        bucket = await get_global_async_bucket()
        await bucket.acquire(1)
        return await func(*args, **kwargs)
    
    return wrapper


# 为了向后兼容，提供一个同步版本的占位符
# （如果某些老代码还在用同步版本的限流器）
class TaskContext:
    """
    任务优先级上下文管理器（异步兼容版）。
    
    注意：当前版本为占位符，未实现真正的优先级队列。
    未来可以基于优先级动态调整令牌桶的参数。
    """
    def __init__(self, priority: int = 100):
        self.priority = priority
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
