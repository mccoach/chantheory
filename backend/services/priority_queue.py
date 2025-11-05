# backend/services/priority_queue.py
# ==============================
# 说明：动态优先级队列（基于MinHeap）
# 职责：
#   1. 支持任务动态插队（按优先级）
#   2. 同优先级按时间FIFO
#   3. 线程安全（asyncio兼容）
# ==============================

from __future__ import annotations

import asyncio
import heapq
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

from backend.utils.logger import get_logger

_LOG = get_logger("priority_queue")

@dataclass(order=True)
class PrioritizedTask:
    """优先级任务（可比较，用于堆排序）"""
    
    priority: int  # 数值越小优先级越高
    timestamp: float = field(compare=True)  # 同优先级按时间
    
    # 实际任务数据（不参与比较）
    data_type_id: str = field(compare=False)
    symbol: Optional[str] = field(default=None, compare=False)
    freq: Optional[str] = field(default=None, compare=False)
    strategy: Optional[dict] = field(default=None, compare=False)
    task_id: Optional[str] = field(default=None, compare=False)

class AsyncPriorityQueue:
    """异步优先级队列"""
    
    def __init__(self):
        self._heap = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()
    
    async def enqueue(self, task: PrioritizedTask):
        """入队（自动按优先级排序）"""
        async with self._lock:
            heapq.heappush(self._heap, task)
            self._not_empty.set()
        
        _LOG.debug(
            f"[队列] 入队 P{task.priority} {task.data_type_id} "
            f"{task.symbol or ''} {task.freq or ''} "
            f"队列长度={len(self._heap)}"
        )
    
    async def dequeue(self) -> Optional[PrioritizedTask]:
        """出队（取优先级最高的）"""
        async with self._lock:
            if not self._heap:
                self._not_empty.clear()
                return None
            
            task = heapq.heappop(self._heap)
            
            if not self._heap:
                self._not_empty.clear()
            
            _LOG.debug(
                f"[队列] 出队 P{task.priority} {task.data_type_id} "
                f"{task.symbol or ''} {task.freq or ''} "
                f"剩余={len(self._heap)}"
            )
            
            return task
    
    async def wait_for_task(self) -> PrioritizedTask:
        """等待任务（阻塞直到有任务）"""
        while True:
            task = await self.dequeue()
            if task is not None:
                return task
            
            # 队列为空，等待新任务
            await self._not_empty.wait()
    
    def size(self) -> int:
        """获取队列长度"""
        return len(self._heap)
    
    def is_empty(self) -> bool:
        """判断队列是否为空"""
        return len(self._heap) == 0

# 全局单例
_global_queue: Optional[AsyncPriorityQueue] = None

def get_priority_queue() -> AsyncPriorityQueue:
    """获取全局优先级队列单例"""
    global _global_queue
    if _global_queue is None:
        _global_queue = AsyncPriorityQueue()
    return _global_queue
