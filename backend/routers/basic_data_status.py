# backend/routers/basic_data_status.py
# ==============================
# 基础数据任务稳定状态路由
#
# 路径：
#   GET /api/system/basic-data-status
#
# 职责：
#   - 提供四大基础数据任务的统一稳定状态快照
#   - 不依赖 SSE 回放
#   - 供前端刷新页面/晚到页面时恢复状态
# ==============================

from __future__ import annotations

from typing import Dict, Any
from fastapi import APIRouter, Request

from backend.services.basic_data_status import get_basic_data_status_snapshot
from backend.utils.errors import http_500_from_exc
from backend.utils.logger import get_logger, log_event

router = APIRouter(prefix="/api/system", tags=["basic-data-status"])
_LOG = get_logger("basic_data_status.router")


@router.get("/basic-data-status")
async def api_basic_data_status(request: Request) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    log_event(
        logger=_LOG,
        service="basic_data_status.router",
        level="INFO",
        file=__file__,
        func="api_basic_data_status",
        line=0,
        trace_id=tid,
        event="api.basic_data_status.start",
        message="GET /api/system/basic-data-status",
    )

    try:
        payload = get_basic_data_status_snapshot()

        log_event(
            logger=_LOG,
            service="basic_data_status.router",
            level="INFO",
            file=__file__,
            func="api_basic_data_status",
            line=0,
            trace_id=tid,
            event="api.basic_data_status.done",
            message="GET /api/system/basic-data-status done",
            extra={"rows": len(payload.get("items") or [])},
        )
        return payload

    except Exception as e:
        log_event(
            logger=_LOG,
            service="basic_data_status.router",
            level="ERROR",
            file=__file__,
            func="api_basic_data_status",
            line=0,
            trace_id=tid,
            event="api.basic_data_status.fail",
            message="GET /api/system/basic-data-status failed",
            extra={"error": str(e)},
        )
        raise http_500_from_exc(e, trace_id=tid)
