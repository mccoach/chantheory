# backend/routers/symbols.py
# ==============================
# 标的索引路由（symbol_index 专项版）
#
# 当前职责：
#   - GET /api/symbols/index   : 返回当前 symbol_index 快照（只读，不刷新）
#   - GET /api/symbols/summary : 标的列表摘要统计
#
# 说明：
#   - symbol_index 作为批量快照表
#   - 不再返回逐行 updated_at
#   - 最近同步时间应统一从基础任务状态接口读取
# ==============================

from __future__ import annotations

import asyncio
from fastapi import APIRouter, Request
from typing import Dict, Any

from backend.utils.errors import http_500_from_exc
from backend.db.connection import get_conn
from backend.utils.logger import get_logger, log_event

router = APIRouter(prefix="/api/symbols", tags=["symbols"])
_LOG = get_logger("symbols.router")


@router.get("/index")
async def api_get_symbol_index(
    request: Request,
) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    log_event(
        logger=_LOG,
        service="symbols.router",
        level="INFO",
        file=__file__,
        func="api_get_symbol_index",
        line=0,
        trace_id=tid,
        event="api.read.start",
        message="GET /symbols/index",
        extra={},
    )

    try:
        db_items = await asyncio.to_thread(_select_symbol_index_only)

        payload = {
            "ok": True,
            "rows": len(db_items),
            "items": db_items,
            "trace_id": tid,
        }

        log_event(
            logger=_LOG,
            service="symbols.router",
            level="INFO",
            file=__file__,
            func="api_get_symbol_index",
            line=0,
            trace_id=tid,
            event="api.read.done",
            message="GET /symbols/index done",
            extra={"rows": len(db_items)},
        )

        return payload

    except Exception as e:
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="ERROR",
            file=__file__,
            func="api_get_symbol_index",
            line=0,
            trace_id=tid,
            event="api.read.fail",
            message="GET /symbols/index failed",
            extra={"error": str(e)},
        )
        raise http_500_from_exc(e, trace_id=tid)


@router.get("/summary")
async def api_symbols_summary(request: Request) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    log_event(
        logger=_LOG,
        service="symbols.router",
        level="INFO",
        file=__file__,
        func="api_symbols_summary",
        line=0,
        trace_id=tid,
        event="api.read.start",
        message="GET /symbols/summary",
    )

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT class, COUNT(*) AS n FROM symbol_index GROUP BY class ORDER BY n DESC;"
        )
        by_class = [{"class": r[0], "n": r[1]} for r in cur.fetchall()]

        cur.execute(
            "SELECT type, COUNT(*) AS n FROM symbol_index GROUP BY type ORDER BY n DESC;"
        )
        by_type = [{"type": r[0], "n": r[1]} for r in cur.fetchall()]

        cur.execute(
            "SELECT type, market, COUNT(*) AS n FROM symbol_index GROUP BY type, market ORDER BY n DESC;"
        )
        by_type_market = [
            {"type": r[0], "market": r[1], "n": r[2]} for r in cur.fetchall()
        ]

        payload = {
            "ok": True,
            "by_class": by_class,
            "by_type": by_type,
            "by_type_market": by_type_market,
            "trace_id": tid,
        }

        log_event(
            logger=_LOG,
            service="symbols.router",
            level="INFO",
            file=__file__,
            func="api_symbols_summary",
            line=0,
            trace_id=tid,
            event="api.read.done",
            message="GET /symbols/summary done",
        )

        return payload

    except Exception as e:
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="ERROR",
            file=__file__,
            func="api_symbols_summary",
            line=0,
            trace_id=tid,
            event="api.read.fail",
            message="GET /symbols/summary failed",
            extra={"error": str(e)},
        )
        raise http_500_from_exc(e, trace_id=tid)


def _select_symbol_index_only() -> list:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            symbol,
            market,
            name,
            class,
            type,
            listing_date
        FROM symbol_index
        ORDER BY market ASC, symbol ASC;
        """
    )

    rows = cur.fetchall()
    return [dict(r) for r in rows]
