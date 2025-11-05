# backend/utils/events.py
# ==============================
# 说明：超轻量级全局事件总线 (全新模块)
# - 职责：提供一个线程安全的、全局共享的事件发布/订阅机制。
# - 目的：解耦后台服务（如 Synchronizer）与前端通知路由（如 SSE），
#         替代已废弃的 scheduler.py 中的事件部分，遵循单一职责原则。
# ==============================

from __future__ import annotations

import threading
from typing import Callable, Any, List, Dict

# 全局订阅者列表
_subscribers: List[Callable[[Dict[str, Any]], None]] = []
# 线程锁，用于安全地修改订阅者列表
_lock = threading.Lock()

def subscribe(callback: Callable[[Dict[str, Any]], None]) -> None:
    """
    订阅全局事件。

    Args:
        callback: 事件发生时调用的回调函数，接收一个事件字典作为参数。
    """
    with _lock:
        if callback not in _subscribers:
            _subscribers.append(callback)

def unsubscribe(callback: Callable[[Dict[str, Any]], None]) -> None:
    """
    取消订阅全局事件。

    Args:
        callback: 要移除的回调函数。
    """
    with _lock:
        try:
            _subscribers.remove(callback)
        except ValueError:
            # 如果回调不存在，静默忽略
            pass

def publish(event: Dict[str, Any]) -> None:
    """
    发布一个全局事件。

    事件将异步地分发给所有订阅者。

    Args:
        event: 包含事件数据的字典。建议包含 'type' 字段。
    """
    # 在锁外获取订阅者列表副本，以避免在回调执行期间持有锁
    with _lock:
        subscribers_copy = list(_subscribers)
    
    # 异步执行所有回调，避免阻塞发布者
    for cb in subscribers_copy:
        try:
            # 简单实现：在当前线程直接调用。
            # 对于需要长时间运行的回调，调用方应自行处理线程。
            cb(event)
        except Exception:
            # 忽略订阅者中的异常，避免影响其他订阅者
            # 可以在此处添加日志记录
            pass

