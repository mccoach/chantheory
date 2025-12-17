# backend/app.py
# ==============================
# FastAPI 应用入口（Task/Job/SSE 版）
#
# 改动：
#   - 启动时的交易日历同步不再直接调用旧配方签名；
#   - 统一构造 Task(type='trade_calendar', scope='global') 并调用 run_trade_calendar(Task)；
#   - Task 内部会发 job_done / task_done 事件，与手动触发保持完全一致；
#   - 其余逻辑保持不变（异步写入器 + 执行器 + SSE 桥接）。
# ==============================

from __future__ import annotations

import asyncio
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
from backend.services.unified_sync_executor import get_sync_executor
from backend.db.async_writer import get_async_writer
from backend.utils.logger import get_logger
from backend.utils.events import (
    subscribe as subscribe_event,
    unsubscribe as unsubscribe_event,
)
from backend.utils.sse_manager import get_sse_manager

# 新增：Task 工具与日历配方
from backend.services.task_model import create_task
from backend.services.data_recipes import run_trade_calendar

_LOG = get_logger("app")

app = FastAPI(title="ChanTheory API", version="8.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = get_sync_executor()
writer = get_async_writer()

# ===== 领域事件 → SSE 桥接（统一出口）=====

_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None


def _forward_event_to_sse(event: Dict[str, Any]) -> None:
    """
    领域事件总线 → SSE 广播桥接器

    职责：
      - 将 utils.events.publish(...) 发布的所有事件，
        通过全局事件循环异步转发到 SSEManager.broadcast。
      - 保持单向依赖：业务模块只关心 publish，SSE 作为观察者。
    """
    global _EVENT_LOOP
    loop = _EVENT_LOOP
    if loop is None:
        # 应用尚未准备好或已关闭，静默丢弃事件（避免在关闭阶段抛异常）
        return

    manager = get_sse_manager()

    async def _broadcast():
        await manager.broadcast(event)

    try:
        loop.call_soon_threadsafe(asyncio.create_task, _broadcast())
    except RuntimeError:
        # 事件循环已关闭或异常，忽略推送（应用正在退出）
        return


@app.on_event("startup")
async def on_startup() -> None:
    """应用启动：初始化数据库 → 启动写入器 → 启动执行器"""

    global _EVENT_LOOP
    _EVENT_LOOP = asyncio.get_running_loop()
    subscribe_event(_forward_event_to_sse)

    _LOG.info("应用启动：开始初始化")

    # 1. 初始化数据库（仅创建 Schema，不做任何业务级同步）
    ensure_initialized()

    # 2. 启动异步写入器
    await writer.start()

    # 3. 启动执行器（Task/Job 执行完全由前端通过 /api/ensure-data 显式触发）
    asyncio.create_task(executor.start())

    _LOG.info("应用启动完成")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """应用关闭时：停止写入器 → 停止执行器"""
    _LOG.info("应用关闭：停止服务")

    # 先注销事件桥接（避免关闭阶段仍有事件尝试推送）
    unsubscribe_event(_forward_event_to_sse)
    global _EVENT_LOOP
    _EVENT_LOOP = None

    # 1. 先停止写入器（确保数据落盘）
    await writer.stop()

    # 2. 再停止执行器
    await executor.stop()


async def sync_trade_calendar_on_startup() -> None:
    """
    启动阶段的交易日历同步（Task/Job/SSE 版 · 已不再在 on_startup 中自动调用）

    说明：
      - 该辅助函数保留用于运维/调试场景下的手工调用；
      - 正式流程中，交易日历同步应通过前端显式调用：
          POST /api/ensure-data
          {
            "type": "trade_calendar",
            "scope": "global",
            "symbol": null,
            "freq": null,
            "adjust": "none",
            "params": { "force_fetch": false }
          }
        由 UnifiedSyncExecutor 调用 run_trade_calendar(Task) 完成。
    """
    _LOG.info("[启动] 交易日历 Task：检查并同步交易日历缺口")

    try:
        # trace_id 标记为 'startup'，source='startup'
        task = create_task(
            type="trade_calendar",
            scope="global",
            symbol=None,
            freq=None,
            adjust="none",
            trace_id="startup",
            params={"force_fetch": False},
            source="startup",
        )
        result = await run_trade_calendar(task)
        updated = bool(result.get("updated"))
        rows = result.get("rows")

        if updated:
            _LOG.info(f"[启动] 交易日历已更新，rows={rows}")
        else:
            _LOG.info("[启动] 交易日历已完备，无需更新")

    except Exception as e:
        _LOG.error(f"[启动] 交易日历同步失败: {e}", exc_info=True)


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
    }


# 路由注册
app.include_router(candles_router)
app.include_router(symbols_router)
app.include_router(user_config_router)
app.include_router(watchlist_router)
app.include_router(events_router)
app.include_router(data_sync_router)
app.include_router(factors_router)
app.include_router(profile_router)
app.include_router(trade_calendar_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )