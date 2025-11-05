# backend/routers/events.py
# ==============================
# 说明：服务端事件推送路由 (Server-Sent Events) (REFACTORED)
# - (FIX) 依赖从已废弃的 `scheduler` 切换到新的全局事件总线 `backend.utils.events`。
# - 职责：提供 /api/events/stream 端点，用于向前端推送实时事件。
# ==============================

from __future__ import annotations

import asyncio
import json
import queue
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from datetime import datetime

# (NEW) 从新的全局事件总线导入订阅函数
from backend.utils.events import subscribe as subscribe_global_events

router = APIRouter(prefix="/api/events", tags=["events"])

# 全局事件队列（线程安全的，用于在同步任务线程和异步SSE协程之间传递事件）
_event_queue = queue.Queue()

def _on_global_event(event_data: dict):
    """
    全局事件回调，将事件放入队列。
    注意：这个函数可能会在任意后台工作线程中被调用。
    """
    _event_queue.put(event_data)

# (MODIFIED) 在模块加载时订阅新的全局事件总线
subscribe_global_events(_on_global_event)

async def event_stream(request: Request) -> AsyncGenerator[str, None]:
    """
    SSE 事件流生成器。
    
    Yields:
        SSE 格式的文本消息：event: xxx\ndata: {...}\n\n
    """
    client_id = id(request)
    
    # 发送连接成功的初始消息
    yield f"event: connected\ndata: {json.dumps({'status': 'ok', 'client_id': client_id, 'ts': datetime.now().isoformat()})}\n\n"
    
    while True:
        # 检查客户端是否断开连接
        if await request.is_disconnected():
            break
        
        try:
            # 非阻塞地从队列获取事件（超时1秒）
            event = _event_queue.get(timeout=1.0)
            
            # 格式化为SSE消息
            event_type = event.pop("type", "message")
            data_json = json.dumps(event, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data_json}\n\n"
            
        except queue.Empty:
            # 队列为空，发送心跳保持连接
            yield f"event: heartbeat\ndata: {json.dumps({'ts': datetime.now().isoformat()})}\n\n"
            await asyncio.sleep(0.1)  # 短暂休眠，避免CPU空转

@router.get("/stream")
async def api_event_stream(request: Request):
    """
    建立SSE连接，向前端推送实时事件。
    
    前端连接示例：
    const eventSource = new EventSource('/api/events/stream');
    eventSource.addEventListener('data_updated', (e) => { ... });
    """
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
