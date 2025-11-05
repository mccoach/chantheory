# backend/routers/user.py
# ==============================
# 说明：用户相关API（V4.0 - 无硬编码版）
# 改动：
#   - 移除对 services/user.py 的依赖
#   - 直接调用数据库和声明式API
# ==============================

from __future__ import annotations

from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.db.watchlist import (
    select_user_watchlist,
    insert_watchlist,
    delete_watchlist
)
from backend.settings import settings, DATA_TYPE_DEFINITIONS
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("user")
router = APIRouter(prefix="/api/user", tags=["user"])

class AddWatchlistRequest(BaseModel):
    symbol: str
    tags: List[str] = []
    sort_order: int = 0

@router.get("/watchlist")
async def get_watchlist(request: Request) -> Dict[str, Any]:
    """获取用户自选池"""
    
    try:
        items = select_user_watchlist()
        return {"ok": True, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/watchlist")
async def add_to_watchlist(
    request: Request,
    payload: AddWatchlistRequest
) -> Dict[str, Any]:
    """添加标的到自选池"""
    
    symbol = payload.symbol
    
    try:
        # 1. 加入自选池
        success = insert_watchlist(
            symbol=symbol,
            source="manual",
            tags=payload.tags,
            sort_order=payload.sort_order
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="添加失败")
        
        # 2. 触发同步任务
        await trigger_watchlist_sync(symbol)
        
        # 3. 返回最新列表
        items = select_user_watchlist()
        
        return {"ok": True, "items": items}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(
    request: Request,
    symbol: str
) -> Dict[str, Any]:
    """从自选池移除标的"""
    
    try:
        success = delete_watchlist(symbol)
        
        if not success:
            raise HTTPException(status_code=404, detail="标的不在自选池中")
        
        items = select_user_watchlist()
        
        return {"ok": True, "items": items}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def trigger_watchlist_sync(symbol: str):
    """触发自选池标的的同步任务"""
    
    from backend.services.data_requirement_parser import get_requirement_parser
    from backend.services.priority_queue import get_priority_queue
    
    parser = get_requirement_parser()
    queue = get_priority_queue()
    
    # 构建需求声明
    includes = []
    
    # 6个频率K线
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
    
    requirements = [{
        'scope': 'symbol',
        'symbol': symbol,
        'includes': includes
    }]
    
    # 解析并入队
    tasks = parser.parse_requirements(requirements)
    
    for task in tasks:
        await queue.enqueue(task)
    
    _LOG.info(f"[自选池变动] 已为 {symbol} 生成 {len(tasks)} 个同步任务")
