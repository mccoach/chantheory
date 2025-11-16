# backend/routers/events.py
# ==============================
# V4.0 - 统一SSE管理器版
# 改动：废弃全局队列，统一使用 sse_manager
# ==============================

from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from datetime import datetime

from backend.utils.sse_manager import get_sse_manager

router = APIRouter(prefix="/api/events", tags=["events"])

async def event_stream(request: Request) -> AsyncGenerator[str, None]:
    """SSE 事件流生成器（统一管理器版）"""
    
    manager = get_sse_manager()
    
    # 注册客户端（关键修复！）
    client_id, client = await manager.register()
    
    try:
        # 发送连接成功消息
        yield f"event: connected\ndata: {json.dumps({'type': 'connected', 'client_id': client_id, 'ts': datetime.now().isoformat()})}\n\n"
        
        while True:
            # 检查客户端是否断开
            if await request.is_disconnected():
                break
            
            try:
                # 从客户端队列获取事件（超时1秒）
                event = await asyncio.wait_for(client.queue.get(), timeout=1.0)
                
                event_type = event.get("type", "message")
                data_json = json.dumps(event, ensure_ascii=False)
                
                yield f"event: {event_type}\ndata: {data_json}\n\n"
                
            except asyncio.TimeoutError:
                # 队列为空，发送心跳
                yield f"event: heartbeat\ndata: {json.dumps({'type': 'heartbeat', 'ts': datetime.now().isoformat()})}\n\n"
    
    finally:
        # 注销客户端
        await manager.unregister(client_id)

@router.get("/stream")
async def api_event_stream(request: Request):
    """建立SSE连接"""
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )