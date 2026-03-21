# backend/db/calendar.py
# ==============================
# 交易日历表操作模块（完整自然日历语义版）
# ==============================

from __future__ import annotations
from typing import List, Dict, Any

from backend.db.connection import get_conn, get_write_lock


def upsert_trade_calendar(records: List[Dict[str, Any]]) -> int:
    """批量插入或更新完整自然日历（串行写锁保护）"""
    if not records:
        return 0

    for rec in records:
        rec["market"] = str(rec.get("market") or "CN").strip().upper() or "CN"
        rec["is_trading_day"] = 1 if int(rec.get("is_trading_day") or 0) == 1 else 0

    sql = """
    INSERT INTO trade_calendar (date, market, is_trading_day)
    VALUES (:date, :market, :is_trading_day)
    ON CONFLICT(date) DO UPDATE SET
        market=excluded.market,
        is_trading_day=excluded.is_trading_day;
    """

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.executemany(sql, records)
        conn.commit()
        return cur.rowcount


def is_trading_day(date_ymd: int, market: str = 'CN') -> bool:
    """判断指定日期是否为交易日"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT is_trading_day FROM trade_calendar WHERE date=? AND market=?;",
        (date_ymd, market)
    )
    result = cur.fetchone()
    return bool(result and result[0] == 1) if result else False


def get_recent_trading_days(n: int = 10, market: str = 'CN') -> List[int]:
    """获取最近N个交易日"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date FROM trade_calendar
        WHERE market=? AND is_trading_day=1
        ORDER BY date DESC
        LIMIT ?;
        """,
        (market, n)
    )
    rows = cur.fetchall()
    return [row[0] for row in rows]


def select_trading_days_in_range(start_ymd: int, end_ymd: int, market: str = 'CN') -> List[int]:
    """查询指定日期范围内的所有交易日"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date FROM trade_calendar
        WHERE market=? AND is_trading_day=1 AND date>=? AND date<=?
        ORDER BY date ASC;
        """,
        (market, start_ymd, end_ymd)
    )
    rows = cur.fetchall()
    return [row[0] for row in rows]
