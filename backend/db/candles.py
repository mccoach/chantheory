# backend/db/candles.py
# ==============================
# 说明：K线数据表操作模块
# - 职责：candles_raw 表的所有CRUD操作
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.db.connection import get_conn
from backend.utils.time import query_range_ms, to_yyyymmdd  # 标准导入

def upsert_candles_raw(records: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新K线数据。
    
    Args:
        records: 字典列表，每个字典包含：
                symbol, freq, ts, open, high, low, close, volume, amount, turnover_rate, source
    
    Returns:
        int: 影响的行数
    """
    if not records:
        return 0
    
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    for rec in records:
        rec['fetched_at'] = rec.get('fetched_at', now)
    
    sql = """
    INSERT INTO candles_raw (symbol, freq, ts, open, high, low, close, volume, amount, turnover_rate, source, fetched_at)
    VALUES (:symbol, :freq, :ts, :open, :high, :low, :close, :volume, :amount, :turnover_rate, :source, :fetched_at)
    ON CONFLICT(symbol, freq, ts) DO UPDATE SET
        open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
        volume=excluded.volume, amount=excluded.amount, turnover_rate=excluded.turnover_rate,
        source=excluded.source, fetched_at=excluded.fetched_at;
    """
    
    cur.executemany(sql, records)
    conn.commit()
    return cur.rowcount


def select_candles_raw(
    symbol: str,
    freq: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    limit: Optional[int] = None,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    查询原始K线数据
    
    时间戳语义规范：
      - start_ts/end_ts: 查询范围（毫秒时间戳）
      - 数据库中的 ts: K线收盘时刻
    
    推荐用法：
      # 查询某日范围
      from backend.utils.time import query_range_ms
      start_ts, end_ts = query_range_ms(20241101, 20241103)
      candles = select_candles_raw(symbol, freq, start_ts, end_ts)
    
    Args:
        symbol: 标的代码
        freq: 频率
        start_ts: 起始时间戳（>=，包含边界）
        end_ts: 结束时间戳（<=，包含边界）
        limit: 返回条数限制
        offset: 偏移量
    
    Returns:
        List[Dict]: K线记录列表
    """
    conn = get_conn()
    cur = conn.cursor()
    
    where_clauses = ["symbol=?", "freq=?"]
    params = [symbol, freq]
    
    if start_ts is not None:
        where_clauses.append("ts>=?")
        params.append(start_ts)
    
    if end_ts is not None:
        where_clauses.append("ts<=?")
        params.append(end_ts)
    
    where_sql = " AND ".join(where_clauses)
    limit_sql = f"LIMIT {limit}" if limit else ""
    offset_sql = f"OFFSET {offset}" if offset > 0 else ""
    
    sql = f"SELECT * FROM candles_raw WHERE {where_sql} ORDER BY ts ASC {limit_sql} {offset_sql};"
    
    cur.execute(sql, params)
    rows = cur.fetchall()
    
    return [dict(r) for r in rows]

def get_latest_ts_from_raw(symbol: str, freq: str) -> Optional[int]:
    """
    获取指定标的+频率的最新时间戳
    
    返回语义：
      最新K线的收盘时刻（毫秒时间戳）
    
    用途：
      缺口判断时对比本地最新数据
    
    Returns:
        Optional[int]: 最新时间戳，无数据返回None
    """
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT MAX(ts) FROM candles_raw WHERE symbol=? AND freq=?;",
        (symbol, freq)
    )
    
    result = cur.fetchone()
    return result[0] if result and result[0] else None
