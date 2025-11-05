# backend/db/watchlist.py
# ==============================
# 说明：用户自选池表操作模块
# - 职责：user_watchlist 表的所有CRUD操作
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from backend.db.connection import get_conn

def insert_watchlist(symbol: str, source: str = "manual", note: str = None, tags: List[str] = None, sort_order: int = 0) -> bool:
    """
    添加标的到自选池（V2.0版：支持tags和sort_order）。
    
    Args:
        symbol: 标的代码
        source: 添加来源，默认 'manual'
        note: 用户备注，可选
        tags: 用户标签列表，如 ['核心', '短线']
        sort_order: 排序权重，数值越小越靠前
    
    Returns:
        bool: 是否成功
    """
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    # tags: 转为JSON字符串
    tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
    
    try:
        cur.execute(
            """
            INSERT INTO user_watchlist (symbol, added_at, source, note, tags, sort_order, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                note=excluded.note,
                tags=excluded.tags,
                sort_order=excluded.sort_order,
                updated_at=excluded.updated_at;
            """,
            (symbol, now, source, note, tags_json, sort_order, now)
        )
        conn.commit()
        return True
    except Exception:
        return False


def delete_watchlist(symbol: str) -> bool:
    """
    从自选池删除标的。
    
    Returns:
        bool: 是否成功
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_watchlist WHERE symbol=?;", (symbol,))
    conn.commit()
    return cur.rowcount > 0


def select_user_watchlist() -> List[Dict[str, Any]]:
    """
    查询用户自选池的所有标的（V2.0版：按sort_order排序）。
    
    Returns:
        List[Dict]: 自选标的列表，已按 sort_order ASC, added_at ASC 排序
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_watchlist ORDER BY sort_order ASC, added_at ASC;")
    rows = cur.fetchall()
    
    results = []
    for row in rows:
        result = dict(row)
        # tags: 解析JSON
        if result.get('tags'):
            try:
                result['tags'] = json.loads(result['tags'])
            except (json.JSONDecodeError, TypeError):
                result['tags'] = []
        else:
            result['tags'] = []
        results.append(result)
    
    return results


def update_watchlist_tags(symbol: str, tags: List[str]) -> bool:
    """
    更新自选池中某标的的tags。
    
    Args:
        symbol: 标的代码
        tags: 新的标签列表
    
    Returns:
        bool: 是否成功
    """
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
    
    cur.execute(
        "UPDATE user_watchlist SET tags=?, updated_at=? WHERE symbol=?;",
        (tags_json, now, symbol)
    )
    conn.commit()
    return cur.rowcount > 0


def update_watchlist_sort_order(symbol: str, sort_order: int) -> bool:
    """
    更新自选池中某标的的排序权重。
    
    Args:
        symbol: 标的代码
        sort_order: 新的排序权重
    
    Returns:
        bool: 是否成功
    """
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    cur.execute(
        "UPDATE user_watchlist SET sort_order=?, updated_at=? WHERE symbol=?;",
        (sort_order, now, symbol)
    )
    conn.commit()
    return cur.rowcount > 0
