# backend/app.py
# ==============================
# FastAPI 应用入口（V6.0 - 集成异步写入器版）
# 改动：
#   - 启动时初始化异步写入器
#   - 关闭时优雅停止写入器（确保数据落盘）
# ==============================

from __future__ import annotations

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from datetime import datetime

from backend.settings import settings
from backend.db import ensure_initialized
from backend.routers.candles import router as candles_router
from backend.routers.symbols import router as symbols_router
from backend.routers.user_config import router as user_config_router
from backend.routers.watchlist import router as watchlist_router
from backend.routers.debug import router as debug_router
from backend.routers.events import router as events_router
from backend.routers.data_sync import router as data_sync_router
from backend.routers.factors import router as factors_router
from backend.services.unified_sync_executor import get_sync_executor
from backend.db.async_writer import get_async_writer  # ← 新增导入
from backend.utils.logger import get_logger

_LOG = get_logger("app")

app = FastAPI(title="ChanTheory API", version="6.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = get_sync_executor()
writer = get_async_writer()  # ← 新增：获取写入器

@app.on_event("startup")
async def on_startup() -> None:
    """应用启动：初始化数据库 → 启动写入器 → 启动执行器"""
    
    _LOG.info("应用启动：开始初始化")
    
    # 1. 初始化数据库
    ensure_initialized()
    
    # 2. 条件同步交易日历
    await sync_trade_calendar_if_needed()
    
    # ===== 3. 启动异步写入器（新增）=====
    await writer.start()
    
    # 4. 启动执行器
    asyncio.create_task(executor.start())
    
    _LOG.info("应用启动完成")

@app.on_event("shutdown")
async def on_shutdown() -> None:
    """应用关闭时：停止写入器 → 停止执行器"""
    _LOG.info("应用关闭：停止服务")
    
    # ===== 1. 先停止写入器（确保数据落盘）=====
    await writer.stop()
    
    # 2. 再停止执行器
    await executor.stop()

async def sync_trade_calendar_if_needed():
    """
    条件同步交易日历
    
    规则：
      - 本地最晚日期 >= 今日 → 跳过（一年拉一次）
      - 本地最晚日期 < 今日 → 拉新（小概率）
    """
    from backend.db.calendar import get_latest_date
    from backend.datasource import dispatcher
    from backend.services.normalizer import normalize_trade_calendar_df
    from backend.db.calendar import upsert_trade_calendar
    from backend.utils.time import today_ymd
    
    _LOG.info("[启动] 检查交易日历缺口")
    
    try:
        # 1. 判断缺口
        local_latest = get_latest_date()
        today = today_ymd()
        
        if local_latest and local_latest >= today:
            _LOG.info(f"[启动] 交易日历已覆盖到 {local_latest}（今日={today}），跳过同步")
            return
        
        _LOG.info(f"[启动] 交易日历需要更新（本地最晚={local_latest or '无'}，今日={today}）")
        
        # 2. 拉取
        raw_df, source_id = await dispatcher.fetch('trade_calendar')
        
        if raw_df is None or raw_df.empty:
            _LOG.error("[启动] 交易日历拉取失败")
            return
        
        # 3. 标准化
        clean_df = normalize_trade_calendar_df(raw_df)
        
        if clean_df is None or clean_df.empty:
            _LOG.error("[启动] 交易日历标准化失败")
            return
        
        # 4. 落库
        records = [
            {
                'date': int(row['date']),
                'market': settings.default_market,
                'is_trading_day': 1
            }
            for _, row in clean_df.iterrows()
        ]
        
        await asyncio.to_thread(upsert_trade_calendar, records)
        
        _LOG.info(f"[启动] 交易日历同步完成，共 {len(records)} 个交易日")
    
    except Exception as e:
        _LOG.error(f"[启动] 交易日历同步失败: {e}")

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
        "writer_queue_size": writer.queue.qsize(),  # ← 新增：写入器队列长度
    }

# 路由注册
app.include_router(candles_router)
app.include_router(symbols_router)
app.include_router(user_config_router)
app.include_router(watchlist_router)
app.include_router(debug_router)
app.include_router(events_router)
app.include_router(data_sync_router)
app.include_router(factors_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host=settings.host, port=settings.port, reload=True)