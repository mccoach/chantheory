# backend/db/factors.py
# ==============================
# 说明：复权因子表操作模块
# 改动：
#   - 新增：compress_factor_records，按 symbol+date 压缩因子记录，仅保留数值变化的日期
#   - upsert_factors：写库前统一调用压缩函数，避免存储冗余
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.db.connection import get_conn

def compress_factor_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    压缩因子记录：
    
    规则（按 symbol 独立处理）：
      - 按 date 升序排序
      - 第一条记录总是保留
      - 之后仅当 (qfq_factor, hfq_factor) 相对上一条发生变化时才保留
      - 缺少 symbol/date 的记录直接保留（容错）
    
    目的：
      - 将“每日一条”的密集因子序列压缩为“因子变化点”的稀疏序列。
      - 配合前端按日期前向填充（ffill），达到同样的复权效果。
    """
    if not records:
        return []
    
    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for rec in records:
        sym = rec.get('symbol')
        grouped.setdefault(sym, []).append(rec)
    
    compressed: List[Dict[str, Any]] = []
    
    for sym, recs in grouped.items():
        # 无法识别 symbol 的记录（sym is None）也分组处理，这类数据通常不应存在，但保持容错
        try:
            recs_sorted = sorted(recs, key=lambda r: r.get('date', 0))
        except Exception:
            # 排序失败，直接保留原序列
            compressed.extend(recs)
            continue
        
        last_q = object()
        last_h = object()
        
        for rec in recs_sorted:
            q = rec.get('qfq_factor')
            h = rec.get('hfq_factor')
            if q != last_q or h != last_h:
                compressed.append(rec)
                last_q, last_h = q, h
            # 若完全相同则跳过（删除冗余行）
    
    return compressed

def upsert_factors(records: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新复权因子数据（V2.0 - 稀疏压缩版）。
    
    行为：
      - 对传入 records 先进行“按 symbol+date 压缩”（仅保留因子变化点）
      - 然后写入 adj_factors（主键：symbol+date）
    
    Args:
        records: 字典列表，每个字典包含：
                symbol, date, qfq_factor, hfq_factor
    
    Returns:
        int: 影响的行数
    """
    if not records:
        return 0
    
    # 先压缩（避免存储密集冗余）
    clean_records = compress_factor_records(records)
    if not clean_records:
        return 0
    
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    for rec in clean_records:
        # 无条件覆盖为 now
        rec["updated_at"] = now
    
    sql = """
    INSERT INTO adj_factors (symbol, date, qfq_factor, hfq_factor, updated_at)
    VALUES (:symbol, :date, :qfq_factor, :hfq_factor, :updated_at)
    ON CONFLICT(symbol, date) DO UPDATE SET
        qfq_factor=excluded.qfq_factor,
        hfq_factor=excluded.hfq_factor,
        updated_at=excluded.updated_at;
    """
    
    cur.executemany(sql, clean_records)
    conn.commit()
    return cur.rowcount


def select_factors(
    symbol: str,
    start_date: Optional[int] = None,
    end_date: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    查询复权因子数据（返回稀疏序列）。
    
    Args:
        symbol: 标的代码
        start_date: 起始日期（YYYYMMDD），可选
        end_date: 结束日期（YYYYMMDD），可选
    
    Returns:
        List[Dict]: 因子记录列表（按 date 升序，通常为稀疏变化点）
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