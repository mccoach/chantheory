# backend/db/candles.py
# ==============================
# 说明：K线数据表操作模块（V3.0 - 联合键修正版）
#
# 职责：
#   - candles_raw 表的所有 CRUD 操作
#
# 本次重构：
#   - 补入 market 维度
#   - 删除 adjust 维度
#   - 主键改为 (market, symbol, freq, ts)
#
# 设计原则：
#   - candles_raw 只存原始不复权K线真相源
#   - 复权应由读取层 / 派生层完成，不在底表做多版本膨胀
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.db.connection import get_conn


def upsert_candles_raw(records: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新 K 线数据（联合键修正版）。

    Args:
        records: 字典列表，每个字典至少包含：
                 market, symbol, freq, ts,
                 open, high, low, close, volume, source
                 可选：
                 amount, turnover_rate

    Returns:
        int: 影响的行数
    """
    if not records:
        return 0

    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()

    prepared: List[Dict[str, Any]] = []
    for rec in records:
        r = dict(rec)

        market = str(r.get("market") or "").strip().upper()
        symbol = str(r.get("symbol") or "").strip()
        freq = str(r.get("freq") or "").strip()

        if market not in ("SH", "SZ", "BJ"):
            raise ValueError(f"upsert_candles_raw: invalid market={market!r}")
        if not symbol:
            raise ValueError("upsert_candles_raw: symbol is required")
        if not freq:
            raise ValueError("upsert_candles_raw: freq is required")

        r["market"] = market
        r["symbol"] = symbol
        r["freq"] = freq
        r["updated_at"] = now
        r["amount"] = r.get("amount")
        r["turnover_rate"] = r.get("turnover_rate")

        prepared.append(r)

    sql = """
    INSERT INTO candles_raw (
        market, symbol, freq, ts,
        open, high, low, close,
        volume, amount, turnover_rate,
        source, updated_at
    )
    VALUES (
        :market, :symbol, :freq, :ts,
        :open, :high, :low, :close,
        :volume, :amount, :turnover_rate,
        :source, :updated_at
    )
    ON CONFLICT(market, symbol, freq, ts) DO UPDATE SET
        open=excluded.open,
        high=excluded.high,
        low=excluded.low,
        close=excluded.close,
        volume=excluded.volume,
        amount=excluded.amount,
        turnover_rate=excluded.turnover_rate,
        source=excluded.source,
        updated_at=excluded.updated_at;
    """

    cur.executemany(sql, prepared)
    conn.commit()
    return cur.rowcount


def select_candles_raw(
    market: str,
    symbol: str,
    freq: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    查询原始 K 线数据（联合键修正版）。

    Args:
        market: 市场（SH/SZ/BJ）
        symbol: 标的代码
        freq: 频率
        start_ts: 起始时间戳（>=，包含边界）
        end_ts: 结束时间戳（<=，包含边界）
        limit: 返回条数限制
        offset: 偏移量

    Returns:
        List[Dict]: K 线记录列表
    """
    conn = get_conn()
    cur = conn.cursor()

    market_u = str(market or "").strip().upper()

    where_clauses = ["market=?", "symbol=?", "freq=?"]
    params: List[Any] = [market_u, symbol, freq]

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
    SELECT * FROM candles_raw
    WHERE {where_sql}
    ORDER BY ts ASC
    {limit_sql} {offset_sql};
    """

    cur.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_latest_ts_from_raw(
    market: str,
    symbol: str,
    freq: str,
) -> Optional[int]:
    """
    获取指定 market+symbol+freq 的最新时间戳。

    Returns:
        Optional[int]: 最新 K 线收盘时刻（毫秒时间戳）
    """
    conn = get_conn()
    cur = conn.cursor()

    market_u = str(market or "").strip().upper()
    cur.execute(
        "SELECT MAX(ts) FROM candles_raw WHERE market=? AND symbol=? AND freq=?;",
        (market_u, symbol, freq),
    )

    result = cur.fetchone()
    return result[0] if result and result[0] else None
