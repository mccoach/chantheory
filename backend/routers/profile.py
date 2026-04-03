# backend/routers/profile.py
# ==============================
# 说明：档案快照路由（profile_snapshot 对应的只读 HTTP 通道）
#
# 路径：
#   GET /api/profile/current?symbol=...&market=...
#
# 行为：
#   - 仅从本地 DB 读取
#   - 不触发 Task，不做任何同步
#   - 按 (symbol, market) 联合主键查询
#
# 本轮改动：
#   - symbol_index / symbol_profile 作为批量快照表
#   - 不再返回逐行 updated_at 相关字段
#   - 最近同步时间应统一从基础任务状态接口读取
# ==============================

from __future__ import annotations

import asyncio
import json
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Query

from backend.db.connection import get_conn
from backend.utils.errors import http_500_from_exc
from backend.utils.logger import get_logger, log_event

router = APIRouter(prefix="/api/profile", tags=["profile"])
_LOG = get_logger("profile.router")


@router.get("/current")
async def api_get_profile_current(
    request: Request,
    symbol: str = Query(..., description="标的代码，如 600519 或 510300"),
    market: str = Query(..., description="市场代码：SH / SZ / BJ"),
    trace_id: Optional[str] = Query(None, description="追踪ID（可选）"),
) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id") or trace_id

    log_event(
        logger=_LOG,
        service="profile.router",
        level="INFO",
        file=__file__,
        func="api_get_profile_current",
        line=0,
        trace_id=tid,
        event="api.profile.current.start",
        message="GET /api/profile/current",
        extra={
            "symbol": symbol,
            "market": market,
        },
    )

    try:
        item = await asyncio.to_thread(_select_profile_for_symbol_market, symbol, market)

        if not item:
            payload = {
                "ok": True,
                "item": None,
                "trace_id": tid,
            }
            log_event(
                logger=_LOG,
                service="profile.router",
                level="INFO",
                file=__file__,
                func="api_get_profile_current",
                line=0,
                trace_id=tid,
                event="api.profile.current.done",
                message="GET /api/profile/current done (not found)",
                extra={
                    "symbol": symbol,
                    "market": market,
                    "found": False,
                },
            )
            return payload

        payload = {
            "ok": True,
            "item": item,
            "trace_id": tid,
        }

        log_event(
            logger=_LOG,
            service="profile.router",
            level="INFO",
            file=__file__,
            func="api_get_profile_current",
            line=0,
            trace_id=tid,
            event="api.profile.current.done",
            message="GET /api/profile/current done",
            extra={
                "symbol": symbol,
                "market": market,
                "found": True,
            },
        )

        return payload

    except Exception as e:
        log_event(
            logger=_LOG,
            service="profile.router",
            level="ERROR",
            file=__file__,
            func="api_get_profile_current",
            line=0,
            trace_id=tid,
            event="api.profile.current.fail",
            message="GET /api/profile/current failed",
            extra={
                "symbol": symbol,
                "market": market,
                "error": str(e),
            },
        )
        raise http_500_from_exc(e, trace_id=tid)


def _select_profile_for_symbol_market(symbol: str, market: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()

    market_u = str(market or "").strip().upper()

    cur.execute(
        """
        SELECT 
            s.symbol,
            s.name,
            s.market,
            s.class,
            s.type,
            s.listing_date,
            p.float_shares,
            p.float_value,
            p.industry,
            p.region,
            p.concepts
        FROM symbol_index s
        LEFT JOIN symbol_profile p
          ON s.symbol = p.symbol AND s.market = p.market
        WHERE s.symbol = ? AND s.market = ?
        LIMIT 1;
        """,
        (symbol, market_u),
    )

    row = cur.fetchone()
    if not row:
        return None

    result = dict(row)

    if result.get("concepts"):
        try:
            result["concepts"] = json.loads(result["concepts"])
            if not isinstance(result["concepts"], list):
                result["concepts"] = []
        except (json.JSONDecodeError, TypeError):
            result["concepts"] = []
    else:
        result["concepts"] = []

    return result
