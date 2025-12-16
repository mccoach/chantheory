# backend/routers/profile.py
# ==============================
# 说明：档案快照路由（current_profile 对应的只读 HTTP 通道）
#
# 职责：
#   - 提供单标的档案快照读取接口：
#       GET /api/profile/current?symbol=...
#   - 数据来源：
#       symbol_index（基础索引字段）
#       LEFT JOIN symbol_profile（档案字段）
#   - 只读：
#       不触发 Task，不做任何远程拉取；
#       前端需先通过 POST /api/ensure-data + type='current_profile'
#       触发档案同步，等 task_done 后再调用本接口读取快照。
#
# 返回约定：
#   - 查到记录：
#       { "ok": true, "item": { ...字段... }, "trace_id": "..." }
#   - 未查到记录（symbol_index 中不存在）：
#       { "ok": true, "item": null, "trace_id": "..." }
#     不抛 404，交由前端决定如何提示。
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
    trace_id: Optional[str] = Query(None, description="追踪ID（可选）"),
) -> Dict[str, Any]:
    """
    获取单个标的的档案快照（current_profile 的只读 HTTP 通道）

    行为说明：
      - 仅从本地 DB 读取，不触发任何 Task 或远程同步；
      - 数据来源：
          symbol_index  基础字段：
            symbol, name, market, class, type, board, listing_date, updated_at
          symbol_profile 档案字段：
            total_shares, float_shares, total_value, nego_value,
            pe_static, industry, region, concepts
      - 若 symbol 在 symbol_index 中不存在：
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
        },
    )

    try:
        item = await asyncio.to_thread(_select_profile_for_symbol, symbol)

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
                "error": str(e),
            },
        )
        raise http_500_from_exc(e, trace_id=tid)


def _select_profile_for_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    """
    从 symbol_index + LEFT JOIN symbol_profile 中查询单标的档案快照。

    Returns:
        dict | None:
          - dict: symbol_index 字段 + 档案字段（concepts 已解析为列表）
          - None: symbol_index 中不存在该标的
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            s.symbol,
            s.name,
            s.market,
            s.class,
            s.type,
            s.board,
            s.listing_date,
            s.updated_at,
            p.total_shares,
            p.float_shares,
            p.total_value,
            p.nego_value,
            p.pe_static,
            p.industry,
            p.region,
            p.concepts
        FROM symbol_index s
        LEFT JOIN symbol_profile p ON s.symbol = p.symbol
        WHERE s.symbol = ?
        LIMIT 1;
        """,
        (symbol,),
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