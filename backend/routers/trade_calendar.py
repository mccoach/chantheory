# backend/routers/trade_calendar.py
# ==============================
# 说明：交易日历快照路由（只读快照，不触发同步）
#
# 路径：
#   - GET /api/trade-calendar
#
# 行为：
#   - 直接从 trade_calendar 表读取所有记录
#   - 不触发任何爬虫或同步任务
#   - 按 date 升序返回：
#       {
#         "ok": true,
#         "items": [
#           { "date": 19901219, "market": "CN", "is_trading_day": 1 },
#           ...
#         ],
#         "trace_id": "..." | null
#       }
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, List

from fastapi import APIRouter, Request

from backend.db.connection import get_conn
from backend.utils.errors import http_500_from_exc
from backend.utils.logger import get_logger, log_event

router = APIRouter(prefix="/api", tags=["trade_calendar"])
_LOG = get_logger("trade_calendar.router")


@router.get("/trade-calendar")
async def api_get_trade_calendar(
    request: Request,
) -> Dict[str, Any]:
    """
    返回 trade_calendar 表的全量快照（只读，不触发同步）

    响应格式：
      {
        "ok": true,
        "items": [
          { "date": 19901219, "market": "CN", "is_trading_day": 1 },
          ...
        ],
        "trace_id": "..." | null
      }
    """
    tid = request.headers.get("x-trace-id")

    log_event(
        logger=_LOG,
        service="trade_calendar.router",
        level="INFO",
        file=__file__,
        func="api_get_trade_calendar",
        line=0,
        trace_id=tid,
        event="api.trade_calendar.start",
        message="GET /trade-calendar",
    )

    try:
        items = await asyncio.to_thread(_select_trade_calendar_all)

        payload: Dict[str, Any] = {
            "ok": True,
            "items": items,
            "trace_id": tid,
        }

        log_event(
            logger=_LOG,
            service="trade_calendar.router",
            level="INFO",
            file=__file__,
            func="api_get_trade_calendar",
            line=0,
            trace_id=tid,
            event="api.trade_calendar.done",
            message="GET /trade-calendar done",
            extra={"rows": len(items)},
        )

        return payload

    except Exception as e:
        log_event(
            logger=_LOG,
            service="trade_calendar.router",
            level="ERROR",
            file=__file__,
            func="api_get_trade_calendar",
            line=0,
            trace_id=tid,
            event="api.trade_calendar.fail",
            message="GET /trade-calendar failed",
            extra={"error": str(e)},
        )
        raise http_500_from_exc(e, trace_id=tid)


def _select_trade_calendar_all() -> List[Dict[str, Any]]:
    """
    从 trade_calendar 表读取全部记录，按 date 升序。

    返回：
      List[Dict[str, Any]]，每项包含：
        - date          (int, YYYYMMDD)
        - market        (str)
        - is_trading_day(int)
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date, market, is_trading_day
        FROM trade_calendar
        ORDER BY date ASC;
        """
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]