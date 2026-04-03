# backend/db/gbbq_events.py
# ==============================
# gbbq 原始事件表操作模块
#
# 职责：
#   - gbbq_events_raw 表的所有 CRUD 操作
#
# 设计原则：
#   - 该表只存 TDX gbbq 原始事件真相源
#   - 保持字段尽量原始、稳定、可复用
#   - 不提前做业务裁剪
#   - 不存逐行 updated_at
#   - 同步时间统一由 data_task_status 承担
# ==============================

from __future__ import annotations

from typing import List, Dict, Any, Optional

from backend.db.connection import get_conn, get_write_lock


def upsert_gbbq_events_raw(records: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新 gbbq 原始事件。

    期望字段：
      - market
      - symbol
      - date
      - category
      - field1
      - field2
      - field3
      - field4
    """
    if not records:
        return 0

    prepared: List[Dict[str, Any]] = []
    for rec in records:
        r = dict(rec)

        market = str(r.get("market") or "").strip().upper()
        symbol = str(r.get("symbol") or "").strip()

        if market not in ("SH", "SZ", "BJ"):
            raise ValueError(f"upsert_gbbq_events_raw: invalid market={market!r}")
        if not symbol:
            raise ValueError("upsert_gbbq_events_raw: symbol is required")

        try:
            date_val = int(r.get("date"))
        except Exception:
            raise ValueError(f"upsert_gbbq_events_raw: invalid date={r.get('date')!r}")

        try:
            category_val = int(r.get("category"))
        except Exception:
            raise ValueError(f"upsert_gbbq_events_raw: invalid category={r.get('category')!r}")

        prepared.append({
            "market": market,
            "symbol": symbol,
            "date": date_val,
            "category": category_val,
            "field1": r.get("field1"),
            "field2": r.get("field2"),
            "field3": r.get("field3"),
            "field4": r.get("field4"),
        })

    sql = """
    INSERT INTO gbbq_events_raw (
        market,
        symbol,
        date,
        category,
        field1,
        field2,
        field3,
        field4
    )
    VALUES (
        :market,
        :symbol,
        :date,
        :category,
        :field1,
        :field2,
        :field3,
        :field4
    )
    ON CONFLICT(market, symbol, date, category) DO UPDATE SET
        field1=excluded.field1,
        field2=excluded.field2,
        field3=excluded.field3,
        field4=excluded.field4;
    """

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.executemany(sql, prepared)
        conn.commit()
        return int(cur.rowcount or 0)


def select_gbbq_events_raw(
    symbol: Optional[str] = None,
    market: Optional[str] = None,
    category: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    查询 gbbq 原始事件。

    过滤维度：
      - symbol
      - market
      - category
    """
    conn = get_conn()
    cur = conn.cursor()

    where = ["1=1"]
    params: List[Any] = []

    if symbol:
        where.append("symbol=?")
        params.append(str(symbol).strip())

    if market:
        where.append("market=?")
        params.append(str(market).strip().upper())

    if category is not None:
        where.append("category=?")
        params.append(int(category))

    where_sql = " AND ".join(where)

    sql = f"""
    SELECT
        market,
        symbol,
        date,
        category,
        field1,
        field2,
        field3,
        field4
    FROM gbbq_events_raw
    WHERE {where_sql}
    ORDER BY market ASC, symbol ASC, date ASC, category ASC;
    """

    cur.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_gbbq_events_row_count() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM gbbq_events_raw;")
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0
