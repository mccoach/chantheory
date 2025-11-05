# backend/utils/limiter.py
# ==============================
# 说明：全局网络请求限流器（全新模块）
# - 核心：一个带优先级的、线程安全的令牌桶限流器。
# - 提供 `@limit_network_io` 装饰器，用于标记需要限流的网络I/O函数。
# - 通过 `TaskContext` 在线程本地存储中传递任务优先级。
# ==============================
from __future__ import annotations

import time
import threading
import heapq
from functools import wraps
from typing import Callable, Any

from backend.settings import settings

# --- 任务上下文，用于传递优先级 ---
_task_context = threading.local()

class TaskContext:
    def __init__(self, priority: int):
        self.priority = priority
        self._previous_priority = None

    def __enter__(self):
        self._previous_priority = getattr(_task_context, 'priority', None)
        _task_context.priority = self.priority
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _task_context.priority = self._previous_priority

def get_current_task_priority() -> int:
    # 默认优先级为最低
    return getattr(_task_context, 'priority', settings.task_priorities.get('historical_sync', 100))


# --- 带优先级的令牌桶限流器 ---
class PriorityTokenBucketLimiter:
    def __init__(self, requests_per_second: float, max_burst_tokens: int):
        self.rate = requests_per_second
        self.capacity = max_burst_tokens
        self._tokens = float(max_burst_tokens)
        self._last_time = time.monotonic()
        self._lock = threading.Lock()
        self._waiters = [] # 使用 heapq 实现优先队列 (priority, event)

    def _add_tokens(self):
        now = time.monotonic()
        elapsed = now - self._last_time
        self._tokens += elapsed * self.rate
        self._tokens = min(self.capacity, self._tokens)
        self._last_time = now

    def acquire(self):
        if not settings.network_limiter_enabled:
            return

        priority = get_current_task_priority()
        event = threading.Event()
        
        with self._lock:
            heapq.heappush(self._waiters, (priority, event))
            self._add_tokens()
            
            # 尝试唤醒一个等待者
            if self._tokens >= 1 and self._waiters:
                # 检查最高优先级的等待者是否是自己
                if self._waiters[0][1] is event:
                    self._tokens -= 1
                    heapq.heappop(self._waiters)
                    event.set()

        # 如果没有被立即唤醒，则等待
        if not event.is_set():
            event.wait()
        
        # 唤醒后重新检查并补充令牌，然后唤醒下一个（如果可能）
        with self._lock:
            self._add_tokens()
            if self._tokens >= 1 and self._waiters:
                next_priority, next_event = heapq.heappop(self._waiters)
                self._tokens -= 1
                next_event.set()


# --- 全局单例和装饰器 ---
global_limiter = PriorityTokenBucketLimiter(
    requests_per_second=settings.network_requests_per_second,
    max_burst_tokens=settings.network_max_burst_tokens
)

def limit_network_io(func: Callable) -> Callable:
    """一个装饰器，用于在函数执行前获取限流许可。"""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        global_limiter.acquire()
        return func(*args, **kwargs)
    return wrapper
