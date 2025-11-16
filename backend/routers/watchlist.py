# backend/routers/watchlist.py
# ==============================
# V6.0 - 自选池异步版（彻底重构）
# 改动：
#   - 文件重命名（user.py → watchlist.py）
#   - URL前缀修改（/api/user → /api/watchlist）
#   - 数据库调用改为异步（避免阻塞）
#   - 查询改为带详细信息（JOIN symbol_index）
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime

from backend.db.watchlist import (
    select_user_watchlist_with_details,
    insert_watchlist,
    delete_watchlist
)
from backend.utils.sse_manager import get_sse_manager
from backend.utils.logger import get_logger

_LOG = get_logger("watchlist")
router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

class AddWatchlistRequest(BaseModel):
    symbol: str
    tags: List[str] = []
    sort_order: int = 0

@router.get("")
async def get_watchlist(request: Request) -> Dict[str, Any]:
    """
    获取自选池（带标的详细信息）
    
    返回字段：
      - symbol, added_at, tags, sort_order（自选池字段）
      - name, market, type, listing_date（标的索引字段）
    """
    try:
        items = await asyncio.to_thread(select_user_watchlist_with_details)
        return {"ok": True, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def add_to_watchlist(
    request: Request,
    payload: AddWatchlistRequest
) -> Dict[str, Any]:
    """
    添加到自选池（异步版，避免阻塞）
    
    流程：
      1. 异步写入数据库
      2. 异步查询最新列表（带详细信息）
      3. 异步广播SSE事件
    """
    
    symbol = payload.symbol
    
    try:
        # 1. 本地写入（异步）
        success = await asyncio.to_thread(
            insert_watchlist,
            symbol=symbol,
            source="manual",
            tags=payload.tags,
            sort_order=payload.sort_order
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="添加失败")
        
        # 2. 获取最新列表（异步 + 带详细信息）
        items = await asyncio.to_thread(select_user_watchlist_with_details)
        
        # 3. 推送SSE（异步）
        manager = get_sse_manager()
        await manager.broadcast({
            'type': 'watchlist_updated',
            'action': 'add',
            'symbol': symbol,
            'items': items,
            'timestamp': datetime.now().isoformat()
        })
        
        _LOG.info(f"[自选池] ✅ 已添加 {symbol}")
        
        return {"ok": True, "items": items}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{symbol}")
async def remove_from_watchlist(
    request: Request,
    symbol: str
) -> Dict[str, Any]:
    """
    从自选池移除（异步版，避免阻塞）
    
    流程：
      1. 异步删除数据库记录
      2. 异步查询最新列表（带详细信息）
      3. 异步广播SSE事件
    """
    
    try:
        # 1. 本地删除（异步）
        success = await asyncio.to_thread(delete_watchlist, symbol)
        
        if not success:
            raise HTTPException(status_code=404, detail="标的不在自选池中")
        
        # 2. 获取最新列表（异步 + 带详细信息）
        items = await asyncio.to_thread(select_user_watchlist_with_details)
        
        # 3. 推送SSE（异步）
        manager = get_sse_manager()
        await manager.broadcast({
            'type': 'watchlist_updated',
            'action': 'remove',
            'symbol': symbol,
            'items': items,
            'timestamp': datetime.now().isoformat()
        })
        
        _LOG.info(f"[自选池] ✅ 已移除 {symbol}")
        
        return {"ok": True, "items": items}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))