# backend/db/candles.py
# ==============================
# 说明：K线数据表操作模块（V2.0 - 带 adjust 维度）
# - 职责：candles_raw 表的所有CRUD操作
# - 改动：
#     * 所有读写均增加 adjust 维度：
#         - adjust: 'none' | 'qfq' | 'hfq'
#     * 主键为 (symbol, freq, ts, adjust)
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.db.connection import get_conn
from backend.utils.time import query_range_ms, to_yyyymmdd  # 标准导入


def upsert_candles_raw(records: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新K线数据（带 adjust 维度）。
    
    Args:
        records: 字典列表，每个字典至少包含：
                 symbol, freq, ts, open, high, low, close, volume, source
                 可选：
                 amount, turnover_rate, fetched_at, adjust('none'|'qfq'|'hfq')
    
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
        # 默认字段填充
        rec = dict(rec)  # 复制一份，避免修改调用方对象

        # updated_at 语义：该记录“本次写入/更新”的时间
        # 无论调用方是否传入、值为何，统一覆盖为 now
        rec["updated_at"] = now

        rec["amount"] = rec.get("amount")
        rec["turnover_rate"] = rec.get("turnover_rate")
        rec["adjust"] = rec.get("adjust", "none") or "none"
        prepared.append(rec)
    
    sql = """
    INSERT INTO candles_raw (
        symbol, freq, ts,
        open, high, low, close,
        volume, amount, turnover_rate,
        source, updated_at, adjust
    )
    VALUES (
        :symbol, :freq, :ts,
        :open, :high, :low, :close,
        :volume, :amount, :turnover_rate,
        :source, :updated_at, :adjust
    )
    ON CONFLICT(symbol, freq, ts, adjust) DO UPDATE SET
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
    symbol: str,
    freq: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    adjust: str = "none",
) -> List[Dict[str, Any]]:
    """
    查询原始K线数据（带 adjust 维度）
    
    时间戳语义规范：
      - start_ts/end_ts: 查询范围（毫秒时间戳）
      - 数据库中的 ts: K线收盘时刻
    
    推荐用法：
      # 查询某日范围
      from backend.utils.time import query_range_ms
      start_ts, end_ts = query_range_ms(20241101, 20241103)
      candles = select_candles_raw(symbol, freq, start_ts, end_ts, adjust='none')
    
    Args:
        symbol: 标的代码
        freq: 频率
        start_ts: 起始时间戳（>=，包含边界）
        end_ts: 结束时间戳（<=，包含边界）
        limit: 返回条数限制
        offset: 偏移量
        adjust: 复权标记：'none' | 'qfq' | 'hfq'
    
    Returns:
        List[Dict]: K线记录列表
    """
    conn = get_conn()
    cur = conn.cursor()
    
    where_clauses = ["symbol=?", "freq=?", "adjust=?"]
    params: List[Any] = [symbol, freq, adjust]
    
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
    symbol: str,
    freq: str,
    adjust: str = "none",
) -> Optional[int]:
    """
    获取指定标的+频率+adjust 的最新时间戳
    
    返回语义：
      最新K线的收盘时刻（毫秒时间戳）
    
    用途：
      缺口判断时对比本地最新数据
    
    Args:
        symbol: 标的代码
        freq: 频率
        adjust: 复权标记：'none' | 'qfq' | 'hfq'
    
    Returns:
        Optional[int]: 最新时间戳，无数据返回None
    """
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT MAX(ts) FROM candles_raw WHERE symbol=? AND freq=? AND adjust=?;",
        (symbol, freq, adjust),
    )
    
    result = cur.fetchone()
    return result[0] if result and result[0] else None