# backend/routers/events.py
# ==============================
# SSE Stream（统一事件名版）
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
    manager = get_sse_manager()
    client_id, client = await manager.register()

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
        await manager.unregister(client_id)


@router.get("/stream")
async def api_event_stream(request: Request):
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
