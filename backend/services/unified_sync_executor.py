# backend/services/unified_sync_executor.py
# ==============================
# V20.1 - Task/Job/SSE 两级模型版（极简执行器 + watchlist_update 支持）
#
# 设计要点：
#   - 不再存在 PrioritizedTask / TaskGroup / data_ready / task_ready 概念；
#   - 执行器只做一件事：
#       * 从 AsyncPriorityQueue 取出 Task（backend.services.task_model.Task）；
#       * 根据 task.type 调用对应配方函数 run_*；
#       * 其他所有“Job 拆解 + SSE(job_done/task_done)”逻辑全部在配方内部完成。
#   - 启动/内部调用也可以直接构造 Task，绕过队列，直接调用配方函数，
#     依然会触发 job_done / task_done 事件（配方内负责）。
# ==============================

from __future__ import annotations

import asyncio
from typing import Optional

from backend.services.priority_queue import get_priority_queue
from backend.services.task_model import Task
from backend.services.data_recipes import (
    run_trade_calendar,
    run_symbol_index,
    run_current_kline,
    run_current_factors,
    run_current_profile,
    run_watchlist_update,
)
from backend.db.async_writer import get_async_writer
from backend.utils.logger import get_logger

_LOG = get_logger("sync_executor")


class UnifiedSyncExecutor:
    """统一同步执行器（极简版）"""

    def __init__(self):
        self.queue = get_priority_queue()
        self.running: bool = False
        self._stop_flag: bool = False
        self.db_writer = get_async_writer()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self):
        """
        启动执行循环：
          - 保证 AsyncDBWriter 已启动；
          - 不断从优先级队列中取出 Task；
          - 调用对应 run_* 配方执行。
        """
        if self.running:
            _LOG.warning("[执行器] 已在运行，忽略重复启动请求")
            return

        self.running = True
        self._stop_flag = False

        # 写入器幂等启动
        await self.db_writer.start()

        _LOG.info("[执行器] 启动任务循环")

        while not self._stop_flag:
            try:
                task = await self.queue.wait_for_task()
                await self._execute_task(task)
            except asyncio.CancelledError:
                _LOG.info("[执行器] 收到取消信号，准备退出")
                break
            except Exception as e:
                _LOG.error("[执行器] 执行任务异常: %s", e, exc_info=True)
                await asyncio.sleep(1.0)

        self.running = False
        _LOG.info("[执行器] 执行循环已停止")

    async def stop(self):
        """
        停止执行器：
          - 置 _stop_flag；
          - 停止 AsyncDBWriter 确保数据落盘。
        """
        self._stop_flag = True
        await self.db_writer.stop()

    # ------------------------------------------------------------------
    # Task 执行
    # ------------------------------------------------------------------

    async def _execute_task(self, task: Task):
        """
        执行单个 Task。

        Job 的拆解与 SSE(job_done/task_done) 事件都在各自的 run_* 配方内完成。
        此处只负责路由与异常兜底日志。
        """
        _LOG.info(
            "[执行器] 开始执行 Task: id=%s type=%s scope=%s symbol=%s freq=%s adjust=%s class=%s",
            task.task_id,
            task.type,
            task.scope,
            task.symbol,
            task.freq,
            task.adjust,
            task.cls,
        )

        try:
            if task.type == "trade_calendar":
                await run_trade_calendar(task)
            elif task.type == "symbol_index":
                await run_symbol_index(task)
            elif task.type == "current_kline":
                await run_current_kline(task)
            elif task.type == "current_factors":
                await run_current_factors(task)
            elif task.type == "current_profile":
                await run_current_profile(task)
            elif task.type == "watchlist_update":
                await run_watchlist_update(task)
            else:
                _LOG.warning(
                    "[执行器] 未知 task.type=%s，task_id=%s，忽略执行",
                    task.type,
                    task.task_id,
                )
        except Exception as e:
            # 各配方内部已经负责发送 job_done/task_done，这里只做兜底日志
            _LOG.error(
                "[执行器] Task 执行异常 task_id=%s type=%s error=%s",
                task.task_id,
                task.type,
                e,
                exc_info=True,
            )
        else:
            _LOG.info(
                "[执行器] Task 执行完成 task_id=%s type=%s",
                task.task_id,
                task.type,
            )


# 全局单例
_executor: Optional[UnifiedSyncExecutor] = None


def get_sync_executor() -> UnifiedSyncExecutor:
    """获取统一同步执行器单例"""
    global _executor
    if _executor is None:
        _executor = UnifiedSyncExecutor()
    return _executor