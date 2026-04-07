# backend/services/unified_sync_executor.py
# ==============================
# 执行器（正式版）
# ==============================

from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any

from backend.settings import settings
from backend.services.priority_queue import get_priority_queue
from backend.services.task_model import Task
from backend.services.data_recipes import (
    run_trade_calendar,
    run_symbol_index,
    run_profile_snapshot,
    run_current_kline,
    run_factor_events_snapshot,
    run_watchlist_update,
)
from backend.db.async_writer import get_async_writer
from backend.utils.logger import get_logger

from backend.services.task_events import emit_task_finished, emit_job_finished

_LOG = get_logger("sync_executor")


def _primary_error(
    *,
    error_code: str,
    error_message: str | None,
    details: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "error_code": str(error_code),
        "error_message": str(error_message) if error_message is not None else None,
        "details": str(details) if details is not None else None,
        "extra": extra or {},
    }


class UnifiedSyncExecutor:
    def __init__(self):
        self.queue = get_priority_queue()
        self.db_writer = get_async_writer()

        self.running: bool = False
        self._stop_flag: bool = False

        self._workers: list[asyncio.Task] = []
        self._started: bool = False

    async def start(self) -> None:
        if self.running:
            _LOG.warning("[执行器] 已在运行，忽略重复启动请求")
            return

        await self.db_writer.start()

        try:
            n = max(1, int(getattr(settings, "executor_concurrency", 1)))
        except Exception:
            n = 1

        self._stop_flag = False
        self.running = True
        self._started = True

        _LOG.info("[执行器] 启动 worker_concurrency=%s", n)

        self._workers = [
            asyncio.create_task(self._worker_loop(i + 1))
            for i in range(n)
        ]

    async def stop(self) -> None:
        if not self._started:
            return
        if self._stop_flag:
            return

        _LOG.info("[执行器] stop requested (graceful)")
        self._stop_flag = True

        try:
            self.queue.close()
        except Exception:
            pass

        workers = list(self._workers)
        if workers:
            try:
                await asyncio.gather(*workers, return_exceptions=True)
            finally:
                self._workers = []

        await self.db_writer.stop()
        self.running = False
        _LOG.info("[执行器] stop completed")

    async def _worker_loop(self, worker_id: int) -> None:
        _LOG.info("[执行器] worker-%s started", worker_id)
        try:
            while True:
                if self._stop_flag:
                    break
                task = await self.queue.wait_for_task()
                if task is None:
                    break
                await self._execute_task(task, worker_id=worker_id)
        except Exception as e:
            _LOG.error("[执行器] worker-%s loop error: %s", worker_id, e, exc_info=True)
        _LOG.info("[执行器] worker-%s stopped", worker_id)

    async def _run_recipe(self, task: Task) -> Optional[Dict[str, Any]]:
        if task.type == "trade_calendar":
            return await run_trade_calendar(task)
        if task.type == "symbol_index":
            return await run_symbol_index(task)
        if task.type == "profile_snapshot":
            return await run_profile_snapshot(task)
        if task.type == "current_kline":
            return await run_current_kline(task)
        if task.type == "factor_events_snapshot":
            return await run_factor_events_snapshot(task)
        if task.type == "watchlist_update":
            return await run_watchlist_update(task)
        return None

    async def _emit_executor_fallback_task_finished(
        self,
        task: Task,
        *,
        error_code: str,
        error_message: str,
        details: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            pe = _primary_error(
                error_code=error_code,
                error_message=error_message,
                details=details,
                extra=extra or {},
            )
            emit_job_finished(
                task,
                job_type="executor_fallback",
                job_index=1,
                job_count=1,
                status="failed",
                result={
                    "rows": 0,
                    "message": error_message,
                    **pe,
                },
            )
            emit_task_finished(
                task,
                jobs={"executor_fallback": "failed"},
                completion_policy="all_required",
                summary={
                    "total_rows": 0,
                    "message": error_message,
                    **pe,
                    "extra": {"primary_error": pe, **(extra or {})},
                },
            )
        except Exception as e:
            _LOG.error("[执行器] fallback task.finished failed: %s", e, exc_info=True)

    async def _execute_task(self, task: Task, worker_id: int = 0) -> None:
        _LOG.info(
            "[执行器] worker-%s execute task_id=%s type=%s scope=%s symbol=%s market=%s freq=%s adjust=%s class=%s",
            worker_id, task.task_id, task.type, task.scope, task.symbol, task.market, task.freq, task.adjust, task.cls,
        )

        timeout_s = float(getattr(settings, "task_timeout_seconds", 30.0) or 30.0)

        try:
            await asyncio.wait_for(self._run_recipe(task), timeout=timeout_s)
        except asyncio.TimeoutError:
            _LOG.error("[执行器] worker-%s task timeout task_id=%s type=%s timeout_s=%s", worker_id, task.task_id, task.type, timeout_s)
            await self._emit_executor_fallback_task_finished(
                task,
                error_code="TASK_TIMEOUT",
                error_message=f"Task timeout after {timeout_s} seconds",
                details="executor wait_for timeout",
                extra={"timeout_s": timeout_s},
            )
        except Exception as e:
            _LOG.error("[执行器] worker-%s task error task_id=%s type=%s error=%s", worker_id, task.task_id, task.type, e, exc_info=True)
            await self._emit_executor_fallback_task_finished(
                task,
                error_code="INTERNAL_ERROR",
                error_message=str(e),
                details="unhandled exception in executor",
                extra={"exception_type": type(e).__name__},
            )
        else:
            _LOG.info("[执行器] worker-%s done task_id=%s type=%s", worker_id, task.task_id, task.type)


_executor: Optional[UnifiedSyncExecutor] = None


def get_sync_executor() -> UnifiedSyncExecutor:
    global _executor
    if _executor is None:
        _executor = UnifiedSyncExecutor()
    return _executor
