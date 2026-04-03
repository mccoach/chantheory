# backend/routers/events.py
# ==============================
# SSE Stream（统一事件名版）
#
# 本轮改动：
#   - 支持按事件类型精确过滤订阅
#   - 路由：
#       GET /api/events/stream?type=a&type=b&type=c
#   - 规则：
#       * 不带 type 参数 -> 保持旧行为：全量订阅
#       * 带 type 参数    -> 仅订阅声明的事件类型
#   - 过滤发生在服务端客户端队列之前，由 SSEManager 负责
# ==============================

from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Optional, List
from datetime import datetime

from backend.utils.sse_manager import get_sse_manager
from backend.utils.logger import get_logger

router = APIRouter(prefix="/api/events", tags=["events"])
_LOG = get_logger("events.router")


async def event_stream(
    request: Request,
    subscribe_types: Optional[List[str]] = None,
) -> AsyncGenerator[str, None]:
    manager = get_sse_manager()
    client_id, client = await manager.register(subscribed_types=subscribe_types)

    try:
        yield f"event: sse.connected\ndata: {json.dumps({'type': 'sse.connected', 'client_id': client_id, 'ts': datetime.now().isoformat()})}\n\n"

        while True:
            if await request.is_disconnected():
                break

            try:
                event = await asyncio.wait_for(client.queue.get(), timeout=1.0)

                event_type = event.get("type", "message")
                data_json = json.dumps(event, ensure_ascii=False)

                yield f"event: {event_type}\ndata: {data_json}\n\n"

            except asyncio.TimeoutError:
                yield f"event: sse.heartbeat\ndata: {json.dumps({'type': 'sse.heartbeat', 'ts': datetime.now().isoformat()})}\n\n"

    finally:
        await manager.unregister(client_id, reason="client_disconnected")


@router.get("/stream")
async def api_event_stream(
    request: Request,
    type: Optional[List[str]] = Query(
        default=None,
        description="按事件类型精确过滤订阅，可重复传参：?type=a&type=b"
    ),
):
    # 清洗订阅类型：
    # - 不带 type -> None -> 全量订阅（兼容旧行为）
    # - 带 type   -> 仅保留非空字符串
    subscribe_types: Optional[List[str]]
    if type is None:
        subscribe_types = None
        _LOG.info("[SSE] 建立全量订阅连接 subscribe_types=None")
    else:
        cleaned = [str(x).strip() for x in type if str(x).strip()]
        subscribe_types = cleaned
        _LOG.info("[SSE] 建立过滤订阅连接 subscribe_types=%s", cleaned)

    return StreamingResponse(
        event_stream(request, subscribe_types=subscribe_types),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
