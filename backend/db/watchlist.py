# backend/db/watchlist.py
# ==============================
# 说明：用户自选池表操作模块
#
# 本轮改动（watchlist 双主键升级）：
#   - watchlist 唯一标识正式升级为 (symbol, market)
#   - 不再允许 symbol-only 增删查改
#   - watchlist 是对 symbol_index 真标的的引用集合，不允许孤儿记录
#
# 当前正式职责：
#   - insert_watchlist
#   - delete_watchlist
#   - select_user_watchlist
#   - select_user_watchlist_with_details
# ==============================

from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime
import json

from backend.db.connection import get_conn

def insert_watchlist(
    symbol: str,
    market: str,
    source: str = "manual",
    note: str = None,
    tags: List[str] = None,
    sort_order: int = 0,
) -> bool:
    """
    添加标的到自选池（双主键版）

    规则：
      - 唯一键为 (symbol, market)
      - 若已存在则幂等成功
      - 仅允许引用 symbol_index 中真实存在的联合键标的
    """
    s = str(symbol or "").strip()
    m = str(market or "").strip().upper()

    if not s or not m:
        return False

    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()

    cur.execute(
        """
        SELECT 1
        FROM symbol_index
        WHERE symbol=? AND market=?
        LIMIT 1;
        """,
        (s, m),
    )
    if cur.fetchone() is None:
        return False

    tags_json = json.dumps(tags, ensure_ascii=False) if tags else None

    try:
        cur.execute(
            """
            INSERT INTO user_watchlist (
                symbol, market, added_at, source, note, tags, sort_order, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, market) DO UPDATE SET
                note=excluded.note,
                tags=excluded.tags,
                sort_order=excluded.sort_order,
                updated_at=excluded.updated_at;
            """,
            (s, m, now, source, note, tags_json, sort_order, now)
        )
        conn.commit()
        return True
    except Exception:
        return False

def delete_watchlist(symbol: str, market: str) -> bool:
    """
    从自选池删除标的（双主键版）
    """
    s = str(symbol or "").strip()
    m = str(market or "").strip().upper()

    if not s or not m:
        return False

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM user_watchlist WHERE symbol=? AND market=?;",
        (s, m),
    )
    conn.commit()
    return cur.rowcount > 0

def select_user_watchlist() -> List[Dict[str, Any]]:
    """
    查询用户自选池的所有标的（双主键版）
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM user_watchlist
        ORDER BY sort_order ASC, added_at ASC, market ASC, symbol ASC;
        """
    )
    rows = cur.fetchall()

    results = []
    for row in rows:
        result = dict(row)
        if result.get('tags'):
            try:
                result['tags'] = json.loads(result['tags'])
            except (json.JSONDecodeError, TypeError):
                result['tags'] = []
        else:
            result['tags'] = []
        results.append(result)

    return results

def select_user_watchlist_with_details() -> List[Dict[str, Any]]:
    """
    查询用户自选池（包含标的详细信息，双主键精确关联）

    返回字段：
      - symbol, market, added_at, source, note, tags, sort_order, updated_at
      - name, class, type, listing_date
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        w.symbol,
        w.market,
        w.added_at,
        w.source,
        w.note,
        w.tags,
        w.sort_order,
        w.updated_at,
        s.name,
        s.class,
        s.type,
        s.listing_date
    FROM user_watchlist w
    INNER JOIN symbol_index s
      ON w.symbol = s.symbol AND w.market = s.market
    ORDER BY w.sort_order ASC, w.added_at ASC, w.market ASC, w.symbol ASC;
    """)

    rows = cur.fetchall()

    results = []
    for row in rows:
        result = dict(row)

        if result.get('tags'):
            try:
                result['tags'] = json.loads(result['tags'])
            except (json.JSONDecodeError, TypeError):
                result['tags'] = []
        else:
            result['tags'] = []

        results.append(result)

    return results