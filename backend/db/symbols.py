# backend/db/symbols.py
# ==============================
# 说明：标的元数据表操作模块（V4.0 - 修复字段默认值）
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional, Iterable
from datetime import datetime
import json

from backend.db.connection import get_conn

# ==============================================================================
# symbol_index 表操作
# ==============================================================================

def upsert_symbol_index(rows: Iterable[Dict[str, Any]]) -> int:
    """
    批量插入或更新标的索引（V2.0版）。
    
    Args:
        rows: 字典列表，每个字典包含：
              - symbol (str): 必需
              - name (str): 必需
              - market (str): 可选
              - type (str): 可选
              - listing_date (int): 可选，V2.0新增
              - status (str): 可选，V2.0新增，默认'active'
              - updated_at (str): 可选
    
    Returns:
        int: 影响的行数
    """
    conn = get_conn()
    cur = conn.cursor()
    
    sql = """
    INSERT INTO symbol_index(symbol, name, market, type, listing_date, status, updated_at)
    VALUES (:symbol, :name, :market, :type, :listing_date, :status, :updated_at)
    ON CONFLICT(symbol) DO UPDATE SET
      name=excluded.name,
      market=excluded.market,
      type=excluded.type,
      listing_date=COALESCE(excluded.listing_date, symbol_index.listing_date),
      status=excluded.status,
      updated_at=excluded.updated_at;
    """
    
    now = datetime.now().isoformat()
    prepared_rows = []
    
    for row in rows:
        if isinstance(row, tuple):
            # 兼容旧格式
            prepared_rows.append({
                'symbol': row[0],
                'name': row[1],
                'market': row[2] if len(row) > 2 else None,
                'type': row[3] if len(row) > 3 else None,
                'listing_date': None,
                'status': 'active',
                'updated_at': row[4] if len(row) > 4 else now,
            })
        else:
            prepared_rows.append({
                'symbol': row.get('symbol'),
                'name': row.get('name'),
                'market': row.get('market'),
                'type': row.get('type'),
                'listing_date': row.get('listing_date'),
                'status': row.get('status', 'active'),
                'updated_at': row.get('updated_at', now),
            })
    
    cur.executemany(sql, prepared_rows)
    conn.commit()
    return cur.rowcount


def select_symbol_index(
    symbol: Optional[str] = None,
    type_filter: Optional[str] = None,
    market_filter: Optional[str] = None,
    status_filter: str = 'active'
) -> List[Dict[str, Any]]:
    """
    查询标的索引。
    
    Args:
        symbol: 指定标的，可选
        type_filter: 类型过滤（A/ETF/LOF），可选
        market_filter: 市场过滤（SH/SZ/BJ），可选
        status_filter: 状态过滤，默认只查询'active'
    
    Returns:
        List[Dict]: 标的索引列表
    """
    conn = get_conn()
    cur = conn.cursor()
    
    where_clauses = []
    params = []
    
    if symbol:
        where_clauses.append("symbol=?")
        params.append(symbol)
    
    if type_filter:
        where_clauses.append("type=?")
        params.append(type_filter)
    
    if market_filter:
        where_clauses.append("market=?")
        params.append(market_filter)
    
    if status_filter:
        where_clauses.append("status=?")
        params.append(status_filter)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    sql = f"SELECT * FROM symbol_index WHERE {where_sql} ORDER BY symbol ASC;"
    
    cur.execute(sql, params)
    rows = cur.fetchall()
    
    return [dict(r) for r in rows]


def get_listing_date(symbol: str) -> Optional[int]:
    """
    获取指定标的的上市日期。
    
    优先从 symbol_index 表查询（V2.0新增字段），
    回退到 symbol_profile 表。
    
    Returns:
        Optional[int]: 上市日期（YYYYMMDD），不存在则返回 None
    """
    conn = get_conn()
    cur = conn.cursor()
    
    # 优先查 symbol_index（避免JOIN）
    cur.execute("SELECT listing_date FROM symbol_index WHERE symbol=?;", (symbol,))
    result = cur.fetchone()
    if result and result[0]:
        return result[0]
    
    # 回退到 symbol_profile
    cur.execute("SELECT listing_date FROM symbol_profile WHERE symbol=?;", (symbol,))
    result = cur.fetchone()
    return result[0] if result and result[0] else None


# ==============================================================================
# symbol_profile 表操作
# ==============================================================================

def upsert_symbol_profile(profiles: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新标的档案（V2.0版：移除intro字段）。
    
    Args:
        profiles: 字典列表，每个字典包含：
                 - symbol (str): 必需
                 - listing_date (int): 可选
                 - total_shares (float): 可选
                 - float_shares (float): 可选
                 - industry (str): 可选
                 - region (str): 可选
                 - concepts (str/list): 可选
                 - updated_at (str): 可选
    
    Returns:
        int: 影响的行数
    """
    if not profiles:
        return 0
    
    conn = get_conn()
    cur = conn.cursor()
    
    sql = """
    INSERT INTO symbol_profile (symbol, listing_date, total_shares, float_shares, industry, region, concepts, updated_at)
    VALUES (:symbol, :listing_date, :total_shares, :float_shares, :industry, :region, :concepts, :updated_at)
    ON CONFLICT(symbol) DO UPDATE SET
        listing_date=COALESCE(excluded.listing_date, symbol_profile.listing_date),
        total_shares=COALESCE(excluded.total_shares, symbol_profile.total_shares),
        float_shares=COALESCE(excluded.float_shares, symbol_profile.float_shares),
        industry=COALESCE(excluded.industry, symbol_profile.industry),
        region=COALESCE(excluded.region, symbol_profile.region),
        concepts=COALESCE(excluded.concepts, symbol_profile.concepts),
        updated_at=excluded.updated_at;
    """
    
    now = datetime.now().isoformat()
    
    for p in profiles:
        p['updated_at'] = p.get('updated_at', now)
        
        # ===== 关键修复：为所有字段提供默认值 =====
        p.setdefault('listing_date', None)
        p.setdefault('total_shares', None)
        p.setdefault('float_shares', None)
        p.setdefault('industry', None)
        p.setdefault('region', None)
        p.setdefault('concepts', None)
        
        # concepts: 如果是列表，转为JSON字符串
        if p.get('concepts') and isinstance(p['concepts'], list):
            p['concepts'] = json.dumps(p['concepts'], ensure_ascii=False)
    
    cur.executemany(sql, profiles)
    conn.commit()
    return cur.rowcount


def select_symbol_profile(symbol: str) -> Optional[Dict[str, Any]]:
    """
    查询单个标的的详细档案。
    
    Returns:
        Optional[Dict]: 档案字典，不存在则返回 None
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM symbol_profile WHERE symbol=?;", (symbol,))
    row = cur.fetchone()
    
    if not row:
        return None
    
    result = dict(row)
    
    # concepts: 如果是JSON字符串，解析为列表
    if result.get('concepts'):
        try:
            result['concepts'] = json.loads(result['concepts'])
        except (json.JSONDecodeError, TypeError):
            pass
    
    return result

# ==============================================================================
# NEW: 查询updated_at相关方法
# ==============================================================================

def get_profile_updated_at(symbol: str) -> Optional[str]:
    """
    获取档案的最后更新时间
    
    Returns:
        Optional[str]: ISO格式时间字符串，不存在返回None
    """
    profile = select_symbol_profile(symbol)
    return profile.get('updated_at') if profile else None
