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
    """
    获取单个标的的档案快照（profile_snapshot 的只读 HTTP 通道）

    行为说明：
      - 仅从本地 DB 读取，不触发任何 Task 或远程同步；
      - 查询语义：按 (symbol, market) 联合主键读取；
      - 若 symbol_index 中不存在该记录：
          返回 ok=true, item=null
      - concepts 字段若为 JSON 字符串，将解析为列表；否则返回空列表。
    """
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
            # 未找到该 symbol，返回 ok=true, item=null
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
    """
    从 symbol_index + LEFT JOIN symbol_profile 中查询单标的档案快照。

    Returns:
        dict | None
    """
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
            s.updated_at AS symbol_index_updated_at,
            p.float_shares,
            p.float_value,
            p.industry,
            p.region,
            p.concepts,
            p.updated_at AS profile_updated_at
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

    # concepts: JSON字符串 → 列表；解析失败或为空时返回空列表
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
