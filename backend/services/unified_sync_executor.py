# backend/services/unified_sync_executor.py
# ==============================
# 执行器（primary_error 对齐版）
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
    run_current_kline,
    run_current_factors,
    run_current_profile,
    run_watchlist_update,
)
from backend.db.async_writer import get_async_writer
from backend.utils.logger import get_logger

from backend.services.task_events import emit_task_finished, emit_job_finished
from backend.db.bulk_batches import (
    get_batch_state_for_client,
    finalize_task_terminal,
)

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
        if task.type == "current_kline":
            return await run_current_kline(task)
        if task.type == "current_factors":
            return await run_current_factors(task)
        if task.type == "current_profile":
            return await run_current_profile(task)
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

    async def _bulk_precheck_cancel_if_stopping(self, task: Task) -> bool:
        md = task.metadata or {}
        batch_id = md.get("batch_id")
        client_task_key = md.get("client_task_key")
        client_instance_id = md.get("client_instance_id")

        if not (isinstance(batch_id, str) and batch_id.strip() and isinstance(client_task_key, str) and client_task_key.strip()):
            return False
        if not (isinstance(client_instance_id, str) and client_instance_id.strip()):
            return False

        bid = batch_id.strip()
        ckey = client_task_key.strip()
        cid = client_instance_id.strip()

        st = await asyncio.to_thread(get_batch_state_for_client, batch_id=bid, client_instance_id=cid)
        if st != "stopping":
            return False

        await asyncio.to_thread(
            finalize_task_terminal,
            batch_id=bid,
            client_task_key=ckey,
            terminal_status="cancelled",
            error_code="USER_CANCELLED",
            error_message="cancelled by user (batch stopping)",
        )

        pe = _primary_error(
            error_code="USER_CANCELLED",
            error_message="cancelled by user",
            details="batch state is stopping; task cancelled before execution",
            extra={"batch_id": bid, "client_task_key": ckey, "batch_state": st},
        )

        emit_job_finished(
            task,
            job_type="executor_bulk_precheck",
            job_index=1,
            job_count=1,
            status="cancelled",
            result={
                "rows": 0,
                "message": "任务已取消（用户终止下载）",
                **pe,
            },
        )
        emit_task_finished(
            task,
            jobs={"executor_bulk_precheck": "cancelled"},
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "任务已取消（用户终止下载）",
                **pe,
                "extra": {"primary_error": pe, "batch_id": bid, "client_task_key": ckey, "batch_state": st},
            },
        )
        return True

    async def _execute_task(self, task: Task, worker_id: int = 0) -> None:
        _LOG.info(
            "[执行器] worker-%s execute task_id=%s type=%s scope=%s symbol=%s freq=%s adjust=%s class=%s",
            worker_id, task.task_id, task.type, task.scope, task.symbol, task.freq, task.adjust, task.cls,
        )

        try:
            if await self._bulk_precheck_cancel_if_stopping(task):
                return
        except Exception as e:
            _LOG.error("[执行器] bulk precheck error: %s", e, exc_info=True)

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
