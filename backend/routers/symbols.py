# backend/routers/symbols.py
# ==============================
# 说明：符号索引路由（最终精简版）
#
# 当前职责：
#   - GET /api/symbols/index   : 返回当前 symbol_index + symbol_profile 快照（只读，不刷新）
#   - GET /api/symbols/summary : 标的列表摘要统计
#
# 刷新标的列表的唯一入口：
#   - POST /api/ensure-data
#       {
#         "type": "symbol_index",
#         "scope": "global",
#         "symbol": null,
#         "freq": null,
#         "adjust": "none",
#         "params": { "force_fetch": true|false }
#       }
#   - 然后等待 SSE 中 task_type='symbol_index' 的 task_done，再 GET /api/symbols/index 读取快照。
# ==============================

from __future__ import annotations

import asyncio
import json
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
    """
    返回标的索引（带档案信息）

    返回字段：
      symbol_index 字段：
        - symbol, name, market, class, type, board, listing_date, updated_at
      symbol_profile 字段：
        - total_shares, float_shares, total_value, nego_value, pe_static, industry, region, concepts

    说明：
      - 本接口仅负责“读取当前索引快照”，不触发任何刷新行为；
      - 刷新统一通过 POST /api/ensure-data + type='symbol_index' 调用 run_symbol_index 完成。
    """
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
        db_items = await asyncio.to_thread(_select_symbol_index_with_profile)

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
    """
    标的列表摘要统计

    返回：
      {
        "ok": true,
        "by_type": [
          { "type": "A", "n": 2000 },
          { "type": "ETF", "n": 500 },
          ...
        ],
        "by_type_market": [
          { "type": "A", "market": "SH", "n": 1000 },
          { "type": "A", "market": "SZ", "n": 1000 },
          { "type": "ETF", "market": "SH", "n": 300 },
          { "type": "ETF", "market": "SZ", "n": 200 },
          ...
        ],
        "trace_id": "..."
      }
    """
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

        # 按 type 统计
        cur.execute(
            "SELECT type, COUNT(*) AS n FROM symbol_index GROUP BY type ORDER BY n DESC;"
        )
        by_type = [{"type": r[0], "n": r[1]} for r in cur.fetchall()]

        # 按 type + market 统计
        cur.execute(
            "SELECT type, market, COUNT(*) AS n FROM symbol_index GROUP BY type, market ORDER BY n DESC;"
        )
        by_type_market = [
            {"type": r[0], "market": r[1], "n": r[2]} for r in cur.fetchall()
        ]

        payload = {
            "ok": True,
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


# ===== 辅助函数：带档案信息的查询 =====
def _select_symbol_index_with_profile() -> list:
    """
    查询标的索引（LEFT JOIN symbol_profile）

    Returns:
        List[Dict]: 包含档案信息的标的列表
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
    ORDER BY s.symbol ASC;
    """
    )

    rows = cur.fetchall()

    results = []
    for row in rows:
        result = dict(row)

        # 解析 concepts（JSON字符串 → 列表）
        if result.get("concepts"):
            try:
                result["concepts"] = json.loads(result["concepts"])
            except (json.JSONDecodeError, TypeError):
                result["concepts"] = []
        else:
            result["concepts"] = []

        results.append(result)

    return results