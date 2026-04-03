# backend/db/candles.py
# ==============================
# 说明：日线数据表操作模块（V4.0 - 日线专用真相源版）
#
# 职责：
#   - candles_day_raw 表的所有 CRUD 操作
#
# 本次重构：
#   - 原 candles_raw 已收缩为日线专用表 candles_day_raw
#   - 删除 freq / turnover_rate / source / updated_at 维度
#   - 主键改为 (market, symbol, ts)
#
# 设计原则：
#   - 该表只存原始不复权日线真相源
#   - 分钟线后续不再进入该表
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional

from backend.db.connection import get_conn


def upsert_candles_day_raw(records: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新日线数据。

    Args:
        records: 字典列表，每个字典至少包含：
                 market, symbol, ts,
                 open, high, low, close, volume
                 可选：
                 amount

    Returns:
        int: 影响的行数
    """
    if not records:
        return 0

    conn = get_conn()
    cur = conn.cursor()

    prepared: List[Dict[str, Any]] = []
    for rec in records:
        r = dict(rec)

        market = str(r.get("market") or "").strip().upper()
        symbol = str(r.get("symbol") or "").strip()

        if market not in ("SH", "SZ", "BJ"):
            raise ValueError(f"upsert_candles_day_raw: invalid market={market!r}")
        if not symbol:
            raise ValueError("upsert_candles_day_raw: symbol is required")

        r["market"] = market
        r["symbol"] = symbol
        r["amount"] = r.get("amount")

        prepared.append(r)

    sql = """
    INSERT INTO candles_day_raw (
        market, symbol, ts,
        open, high, low, close,
        volume, amount
    )
    VALUES (
        :market, :symbol, :ts,
        :open, :high, :low, :close,
        :volume, :amount
    )
    ON CONFLICT(market, symbol, ts) DO UPDATE SET
        open=excluded.open,
        high=excluded.high,
        low=excluded.low,
        close=excluded.close,
        volume=excluded.volume,
        amount=excluded.amount;
    """

    cur.executemany(sql, prepared)
    conn.commit()
    return cur.rowcount


def select_candles_day_raw(
    market: str,
    symbol: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    查询原始日线数据。

    Args:
        market: 市场（SH/SZ/BJ）
        symbol: 标的代码
        start_ts: 起始时间戳（>=，包含边界）
        end_ts: 结束时间戳（<=，包含边界）
        limit: 返回条数限制
        offset: 偏移量

    Returns:
        List[Dict]: 日线记录列表
    """
    conn = get_conn()
    cur = conn.cursor()

    market_u = str(market or "").strip().upper()

    where_clauses = ["market=?", "symbol=?"]
    params: List[Any] = [market_u, symbol]

    if start_ts is not None:
        where_clauses.append("ts>=?")
        params.append(start_ts)

    if end_ts is not None:
        where_clauses.append("ts<=?")
        params.append(end_ts)

    where_sql = " AND ".join(where_clauses)
    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    offset_sql = f"OFFSET {int(offset)}" if offset > 0 else ""

    sql = f"""
    SELECT * FROM candles_day_raw
    WHERE {where_sql}
    ORDER BY ts ASC
    {limit_sql} {offset_sql};
    """

    cur.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_latest_ts_from_day_raw(
    market: str,
    symbol: str,
) -> Optional[int]:
    """
    获取指定 market+symbol 的最新日线时间戳。

    Returns:
        Optional[int]: 最新日线收盘时刻（毫秒时间戳）
    """
    conn = get_conn()
    cur = conn.cursor()

    market_u = str(market or "").strip().upper()
    cur.execute(
        "SELECT MAX(ts) FROM candles_day_raw WHERE market=? AND symbol=?;",
        (market_u, symbol),
    )

    result = cur.fetchone()
    return result[0] if result and result[0] else None
