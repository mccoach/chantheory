# backend/app.py
# ==============================
# FastAPI 应用入口（Task/Job/SSE 版）
# ==============================

from __future__ import annotations

import asyncio
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
from datetime import datetime

from backend.settings import settings
from backend.db import ensure_initialized
from backend.routers.candles import router as candles_router
from backend.routers.symbols import router as symbols_router
from backend.routers.user_config import router as user_config_router
from backend.routers.watchlist import router as watchlist_router
from backend.routers.events import router as events_router
from backend.routers.data_sync import router as data_sync_router
from backend.routers.factors import router as factors_router
from backend.routers.profile import router as profile_router
from backend.routers.trade_calendar import router as trade_calendar_router
from backend.routers.server_identity import router as server_identity_router

from backend.services.unified_sync_executor import get_sync_executor
from backend.db.async_writer import get_async_writer
from backend.utils.logger import get_logger
from backend.utils.events import (
    subscribe as subscribe_event,
    unsubscribe as unsubscribe_event,
    publish as publish_event,
)
from backend.utils.sse_manager import get_sse_manager

from backend.services.server_identity import init_backend_instance_id
from backend.db.bulk_batches import recover_incomplete_batches_to_paused, gc_delete_terminal_tasks

_LOG = get_logger("app")

app = FastAPI(title="ChanTheory API", version="8.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = get_sync_executor()
writer = get_async_writer()

_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None
_RUNTIME_METRICS_TASK: Optional[asyncio.Task] = None


def _forward_event_to_sse(event: Dict[str, Any]) -> None:
    global _EVENT_LOOP
    loop = _EVENT_LOOP
    if loop is None:
        return

    manager = get_sse_manager()

    async def _broadcast():
        await manager.broadcast(event)

    try:
        loop.call_soon_threadsafe(asyncio.create_task, _broadcast())
    except RuntimeError:
        return


async def _runtime_metrics_loop() -> None:
    last: Dict[str, Any] = {}

    try:
        interval = float(getattr(settings, "runtime_metrics_interval_seconds", 1.0) or 1.0)
        if interval <= 0:
            interval = 1.0
    except Exception:
        interval = 1.0

    while True:
        try:
            thread_count = int(threading.active_count())
            payload = {
                "type": "runtime.metrics",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "thread_count": thread_count,
                    "executor_running": bool(executor.running),
                    "queue_size": int(executor.queue.size()),
                    "writer_queue_size": int(writer.queue.qsize()),
                },
            }

            if payload["metrics"] != last:
                publish_event(payload)
                last = dict(payload["metrics"])

            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(interval)


@app.on_event("startup")
async def on_startup() -> None:
    global _EVENT_LOOP
    _EVENT_LOOP = asyncio.get_running_loop()
    subscribe_event(_forward_event_to_sse)

    beid = init_backend_instance_id()
    _LOG.info("backend_instance_id=%s", beid)

    _LOG.info("应用启动：开始初始化")

    ensure_initialized()

    try:
        n = await asyncio.to_thread(recover_incomplete_batches_to_paused, purpose="after_hours")
        if n:
            _LOG.info("[bulk] recover paused: %s batches", n)
    except Exception as e:
        _LOG.error("[bulk] recover failed: %s", e, exc_info=True)

    try:
        days = int(getattr(settings, "after_hours_tasks_retention_days", 2))
        deleted = await asyncio.to_thread(
            gc_delete_terminal_tasks,
            retention_days=days,
            purpose="after_hours",
        )
        if deleted:
            _LOG.info("[bulk] GC deleted bulk_tasks rows=%s (retention_days=%s)", deleted, days)
    except Exception as e:
        _LOG.error("[bulk] GC failed: %s", e, exc_info=True)

    await writer.start()

    asyncio.create_task(executor.start())

    global _RUNTIME_METRICS_TASK
    _RUNTIME_METRICS_TASK = asyncio.create_task(_runtime_metrics_loop())

    _LOG.info("应用启动完成")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    _LOG.info("应用关闭：停止服务")

    unsubscribe_event(_forward_event_to_sse)
    global _EVENT_LOOP
    _EVENT_LOOP = None

    global _RUNTIME_METRICS_TASK
    if _RUNTIME_METRICS_TASK:
        try:
            _RUNTIME_METRICS_TASK.cancel()
            await _RUNTIME_METRICS_TASK
        except Exception:
            pass
        _RUNTIME_METRICS_TASK = None

    await writer.stop()
    await executor.stop()


@app.get("/api/ping")
def ping() -> Dict[str, Any]:
    return {"ok": True, "msg": "pong"}


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "time": datetime.now().isoformat(),
        "timezone": settings.timezone,
        "executor_running": executor.running,
        "queue_size": executor.queue.size(),
        "writer_queue_size": writer.queue.qsize(),
        "thread_count": int(threading.active_count()),
    }


app.include_router(candles_router)
app.include_router(symbols_router)
app.include_router(user_config_router)
app.include_router(watchlist_router)
app.include_router(events_router)
app.include_router(data_sync_router)
app.include_router(factors_router)
app.include_router(profile_router)
app.include_router(trade_calendar_router)
app.include_router(server_identity_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
