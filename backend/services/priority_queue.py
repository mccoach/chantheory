# backend/services/priority_queue.py
# ==============================
# 说明：异步优先级队列（Task 版）
#
# 改动（V3.1 - 支持优雅停机的 close 语义）：
#   - 新增 close()/is_closed()：
#       * close()：标记队列关闭，并唤醒所有等待者
#       * wait_for_task()：队列空且已关闭时返回 None，供 worker 退出
#   - 目的：
#       * 执行器 stop 时不再依赖“超时轮询”(wait_for+TimeoutError)，避免异常风暴与内存上涨
#       * 让 worker 真正阻塞等待任务，同时又能被 stop 立即唤醒退出
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

        # 队列关闭标记：用于优雅停机唤醒 waiters
        self._closed: bool = False

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
        if self._closed:
            # 关闭后不再接受新任务（避免 stop 后仍入队导致无法退出）
            _LOG.warning("[队列] enqueue ignored because queue is closed task_id=%s", task.task_id)
            return

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
        """出队（取优先级最高的 Task）；队列空时返回 None"""
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

    async def wait_for_task(self) -> Optional[Task]:
        """
        阻塞等待，直到队列中有 Task 或队列被 close()。

        Returns:
          - Task: 取到任务
          - None: 队列已关闭且当前为空（用于 worker 退出）
        """
        while True:
            # 先尝试取一次
            task = await self.dequeue()
            if task is not None:
                return task

            # 队列空：如果已关闭，则退出
            if self._closed:
                return None

            # 等待入队事件唤醒
            await self._not_empty.wait()

    def close(self) -> None:
        """
        关闭队列并唤醒所有等待者（用于优雅停机）。

        语义：
          - close 后不再接受新任务（enqueue 会被忽略并 warning）
          - wait_for_task 在队列空时会返回 None
        """
        self._closed = True
        self._not_empty.set()

    def is_closed(self) -> bool:
        return self._closed

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
