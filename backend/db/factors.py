# backend/db/factors.py
# ==============================
# 说明：复权因子表操作模块
# 改动：新增查询updated_at的方法
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.db.connection import get_conn

def upsert_factors(records: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新复权因子数据。
    
    Args:
        records: 字典列表，每个字典包含：
                symbol, date, qfq_factor, hfq_factor
    
    Returns:
        int: 影响的行数
    """
    if not records:
        return 0
    
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    for rec in records:
        rec['updated_at'] = rec.get('updated_at', now)
    
    sql = """
    INSERT INTO adj_factors (symbol, date, qfq_factor, hfq_factor, updated_at)
    VALUES (:symbol, :date, :qfq_factor, :hfq_factor, :updated_at)
    ON CONFLICT(symbol, date) DO UPDATE SET
        qfq_factor=excluded.qfq_factor,
        hfq_factor=excluded.hfq_factor,
        updated_at=excluded.updated_at;
    """
    
    cur.executemany(sql, records)
    conn.commit()
    return cur.rowcount


def select_factors(
    symbol: str,
    start_date: Optional[int] = None,
    end_date: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    查询复权因子数据。
    
    Args:
        symbol: 标的代码
        start_date: 起始日期（YYYYMMDD），可选
        end_date: 结束日期（YYYYMMDD），可选
    
    Returns:
        List[Dict]: 因子记录列表
    """
    conn = get_conn()
    cur = conn.cursor()
    
    where_clauses = ["symbol=?"]
    params = [symbol]
    
    if start_date is not None:
        where_clauses.append("date>=?")
        params.append(start_date)
    
    if end_date is not None:
        where_clauses.append("date<=?")
        params.append(end_date)
    
    where_sql = " AND ".join(where_clauses)
    sql = f"SELECT * FROM adj_factors WHERE {where_sql} ORDER BY date ASC;"
    
    cur.execute(sql, params)
    rows = cur.fetchall()
    
    return [dict(r) for r in rows]


def get_latest_factor_date(symbol: str) -> Optional[int]:
    """
    获取指定标的的最新复权因子日期。
    
    Returns:
        Optional[int]: 最新日期（YYYYMMDD），不存在则返回 None
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) FROM adj_factors WHERE symbol=?;", (symbol,))
    result = cur.fetchone()
    return result[0] if result and result[0] else None

# ==============================================================================
# NEW: 查询updated_at相关方法
# ==============================================================================

def get_factors_latest_updated_at(symbol: str) -> Optional[str]:
    """
    获取因子的最后更新时间
    
    Returns:
        Optional[str]: ISO格式时间字符串，不存在返回None
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT MAX(updated_at) FROM adj_factors WHERE symbol=?;",
        (symbol,)
    )
    result = cur.fetchone()
    return result[0] if result and result[0] else None
