# backend/db/calendar.py
# ==============================
# 说明：交易日历表操作模块
# - 职责：trade_calendar 表的所有CRUD操作
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta

from backend.db.connection import get_conn

def upsert_trade_calendar(records: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新交易日历。
    
    Args:
        records: 字典列表，每个字典包含：
                date (int): YYYYMMDD
                market (str): 市场标识，默认 'CN'
                is_trading_day (int): 1=交易日, 0=非交易日
    
    Returns:
        int: 影响的行数
    """
    if not records:
        return 0
    
    conn = get_conn()
    cur = conn.cursor()
    
    sql = """
    INSERT INTO trade_calendar (date, market, is_trading_day)
    VALUES (:date, :market, :is_trading_day)
    ON CONFLICT(date) DO UPDATE SET
        market=excluded.market,
        is_trading_day=excluded.is_trading_day;
    """
    
    for rec in records:
        rec['market'] = rec.get('market', 'CN')
    
    cur.executemany(sql, records)
    conn.commit()
    return cur.rowcount


def is_trading_day(date_ymd: int, market: str = 'CN') -> bool:
    """
    判断指定日期是否为交易日。
    
    Args:
        date_ymd: 日期（YYYYMMDD）
        market: 市场标识，默认 'CN'
    
    Returns:
        bool: True=交易日, False=非交易日或数据不存在
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT is_trading_day FROM trade_calendar WHERE date=? AND market=?;",
        (date_ymd, market)
    )
    result = cur.fetchone()
    return bool(result and result[0] == 1) if result else False


def get_recent_trading_days(n: int = 10, market: str = 'CN') -> List[int]:
    """
    获取最近N个交易日的日期列表（倒序）。
    
    Args:
        n: 数量
        market: 市场标识
    
    Returns:
        List[int]: 交易日列表（YYYYMMDD），按日期倒序
    """
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
    """
    查询指定日期范围内的所有交易日。
    
    Returns:
        List[int]: 交易日列表（YYYYMMDD），按日期升序
    """
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
