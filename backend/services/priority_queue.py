# backend/services/priority_queue.py
# ==============================
# 说明：异步优先级队列（Task 版）
#
# 改动（V3.0）：
#   - 移除 PrioritizedTask / TaskGroup 结构；
#   - 队列元素仅为 Task（backend.services.task_model.Task）；
#   - 优先级与时间戳从 Task.metadata 中读取：
#       * priority : metadata['priority']，默认 100
#       * created_at: metadata['created_at'] ISO 字符串 → timestamp，用于 FIFO
# ==============================

from __future__ import annotations

import asyncio
import heapq
from datetime import datetime
from typing import Optional, Tuple

from backend.services.task_model import Task
from backend.utils.logger import get_logger

_LOG = get_logger("priority_queue")


class AsyncPriorityQueue:
    """异步 Task 优先级队列"""

    def __init__(self):
        # 堆元素结构：(priority:int, timestamp:float, Task)
        self._heap: list[Tuple[int, float, Task]] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()

    def _extract_priority_and_ts(self, task: Task) -> Tuple[int, float]:
        """从 Task.metadata 中提取 priority 与 created_at；失败时使用兜底值。"""
        md = task.metadata or {}
        prio = int(md.get("priority", 100))

        created_at = md.get("created_at")
        if isinstance(created_at, str):
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                ts = dt.timestamp()
            except Exception:
                ts = datetime.now().timestamp()
        else:
            ts = datetime.now().timestamp()

        return prio, ts

    async def enqueue(self, task: Task):
        """入队 Task（按 priority + created_at 排序）"""
        prio, ts = self._extract_priority_and_ts(task)

        async with self._lock:
            heapq.heappush(self._heap, (prio, ts, task))
            self._not_empty.set()

        _LOG.debug(
            "[队列] 入队 P%s task_id=%s type=%s symbol=%s freq=%s scope=%s 当前长度=%s",
            prio,
            task.task_id,
            task.type,
            task.symbol,
            task.freq,
            task.scope,
            len(self._heap),
        )

    async def dequeue(self) -> Optional[Task]:
        """出队（取优先级最高的 Task）"""
        async with self._lock:
            if not self._heap:
                self._not_empty.clear()
                return None

            prio, ts, task = heapq.heappop(self._heap)

            if not self._heap:
                self._not_empty.clear()

            _LOG.debug(
                "[队列] 出队 P%s task_id=%s type=%s symbol=%s freq=%s scope=%s 剩余=%s",
                prio,
                task.task_id,
                task.type,
                task.symbol,
                task.freq,
                task.scope,
                len(self._heap),
            )

            return task

    async def wait_for_task(self) -> Task:
        """阻塞等待，直到队列中有 Task"""
        while True:
            task = await self.dequeue()
            if task is not None:
                return task

            await self._not_empty.wait()

    def size(self) -> int:
        """返回当前队列长度"""
        return len(self._heap)

    def is_empty(self) -> bool:
        """队列是否为空"""
        return not self._heap


# 全局单例
_global_queue: Optional[AsyncPriorityQueue] = None


def get_priority_queue() -> AsyncPriorityQueue:
    """获取全局优先级队列单例"""
    global _global_queue
    if _global_queue is None:
        _global_queue = AsyncPriorityQueue()
    return _global_queue