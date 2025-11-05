# backend/app.py
# ==============================
# 说明：FastAPI 应用入口（V4.0 - 清理废弃依赖）
# 改动：
#   - 移除 status_router（已删除）
#   - 优化启动逻辑
# ==============================

from __future__ import annotations

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from datetime import datetime

from backend.settings import settings, DATA_TYPE_DEFINITIONS
from backend.db import ensure_initialized
from backend.routers.candles import router as candles_router
from backend.routers.symbols import router as symbols_router
from backend.routers.user_config import router as user_config_router
from backend.routers.user import router as user_router
from backend.routers.debug import router as debug_router
from backend.routers.events import router as events_router
from backend.routers.data_sync import router as data_sync_router
from backend.services.unified_sync_executor import get_sync_executor
from backend.utils.logger import get_logger

_LOG = get_logger("app")

app = FastAPI(title="ChanTheory API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = get_sync_executor()

@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时：初始化数据库并触发首次同步"""
    
    _LOG.info("应用启动：开始初始化")
    
    # 1. 初始化数据库
    ensure_initialized()
    
    # 2. 优先同步交易日历（阻塞等待，确保后续缺口判断可用）
    await sync_trade_calendar_blocking()
    
    # 3. 启动执行器（后台任务消费循环）
    asyncio.create_task(executor.start())
    
    # 4. 触发启动时的数据需求
    await trigger_startup_sync()
    
    _LOG.info("应用启动完成")

@app.on_event("shutdown")
async def on_shutdown() -> None:
    """应用关闭时：安全停止执行器"""
    _LOG.info("应用关闭：停止执行器")
    await executor.stop()

async def sync_trade_calendar_blocking():
    """
    同步交易日历（阻塞版，优先执行）
    
    职责：
      在启动时第一时间拉取交易日历并落库，
      确保后续的缺口判断函数能查到交易日数据。
    """
    from backend.datasource import dispatcher
    from backend.services.normalizer import normalize_trade_calendar_df
    from backend.db.calendar import upsert_trade_calendar
    
    _LOG.info("[启动] 开始同步交易日历（阻塞）")
    
    try:
        # 拉取
        raw_df, source_id = await dispatcher.fetch('trade_calendar')
        
        if raw_df is None or raw_df.empty:
            _LOG.error("[启动] 交易日历拉取失败")
            return
        
        # 标准化
        clean_df = normalize_trade_calendar_df(raw_df)
        
        if clean_df is None or clean_df.empty:
            _LOG.error("[启动] 交易日历标准化失败")
            return
        
        # 转为记录格式
        records = [
            {
                'date': int(row['date']),
                'market': settings.default_market,
                'is_trading_day': 1
            }
            for _, row in clean_df.iterrows()
        ]
        
        # 落库（阻塞等待）
        await asyncio.to_thread(upsert_trade_calendar, records)
        
        _LOG.info(f"[启动] 交易日历同步完成，共 {len(records)} 个交易日")
    
    except Exception as e:
        _LOG.error(f"[启动] 交易日历同步失败: {e}")

async def trigger_startup_sync():
    """触发启动时的数据同步"""
    
    from backend.services.data_requirement_parser import get_requirement_parser
    from backend.services.priority_queue import get_priority_queue
    from backend.db.watchlist import select_user_watchlist
    
    parser = get_requirement_parser()
    queue = get_priority_queue()
    
    # 获取自选池
    watchlist = select_user_watchlist()
    watchlist_symbols = [w['symbol'] for w in watchlist]
    
    # 构建启动时的数据需求声明
    requirements = []
    
    # 需求1：标的列表
    requirements.append({
        'scope': 'global',
        'includes': [{
            'type': 'symbol_index',
            'priority': DATA_TYPE_DEFINITIONS['symbol_index']['priority']
        }]
    })
    
    # 需求2：自选池数据
    if watchlist_symbols:
        includes = []
        
        # 6个频率
        for freq in settings.sync_standard_freqs:
            dt_id = f'watchlist_kline_{freq}'
            includes.append({
                'type': dt_id,
                'freq': freq,
                'priority': DATA_TYPE_DEFINITIONS[dt_id]['priority']
            })
        
        # 档案和因子
        includes.append({
            'type': 'watchlist_profile',
            'priority': DATA_TYPE_DEFINITIONS['watchlist_profile']['priority']
        })
        includes.append({
            'type': 'watchlist_factors',
            'priority': DATA_TYPE_DEFINITIONS['watchlist_factors']['priority']
        })
        
        requirements.append({
            'scope': 'watchlist',
            'symbols': watchlist_symbols,
            'includes': includes
        })
    
    # 需求3：全量档案补缺（P40）
    # 注意：这个需求会生成大量任务，放在最后
    requirements.append({
        'scope': 'all_symbols',
        'includes': [{
            'type': 'all_symbols_profile',
            'priority': DATA_TYPE_DEFINITIONS['all_symbols_profile']['priority']
        }]
    })
    
    # 解析并入队
    tasks = parser.parse_requirements(requirements)
    
    for task in tasks:
        await queue.enqueue(task)
    
    _LOG.info(f"[启动同步] 已生成 {len(tasks)} 个任务")

@app.get("/api/ping")
def ping() -> Dict[str, Any]:
    return {"ok": True, "msg": "pong"}

@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "time": datetime.now().isoformat(),
        "timezone": settings.timezone,
        "db_path": str(settings.db_path) if settings.debug else "[hidden]",
        "executor_running": executor.running,
        "queue_size": executor.queue.size(),
    }

app.include_router(candles_router)
app.include_router(symbols_router)
app.include_router(user_config_router)
app.include_router(user_router)
app.include_router(debug_router)
app.include_router(events_router)
app.include_router(data_sync_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host=settings.host, port=settings.port, reload=True)
