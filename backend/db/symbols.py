# backend/db/symbols.py
# ==============================
# 说明：标的元数据表操作模块（symbol_index 专项重构版）
#
# 本轮目标：
#   - 仅围绕 symbol_index 完成新结构改造
#   - 新结构：
#       symbol + market 联合主键
#       字段：symbol, market, name, class, type, listing_date, updated_at
#
# 注意：
#   - 本轮严格控制范围，不扩散到 symbol_profile 的联合主键重构
#   - symbol_profile 相关函数先保持现状
# ==============================

from __future__ import annotations

from typing import List, Dict, Any, Optional, Iterable
from datetime import datetime
import json

from backend.db.connection import get_conn, get_write_lock

# ==============================================================================
# symbol_index 表操作
# ==============================================================================

def upsert_symbol_index(rows: Iterable[Dict[str, Any]]) -> int:
    """
    批量插入或更新标的索引（联合主键版）

    期望字段：
      - symbol
      - market
      - name
      - class
      - type
      - listing_date
      - updated_at（调用方可省略，由本函数统一覆盖）
    """
    rows = list(rows or [])
    if not rows:
        return 0

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        sql = """
        INSERT INTO symbol_index(
            symbol,
            name,
            market,
            class,
            type,
            listing_date,
            updated_at
        )
        VALUES (
            :symbol,
            :name,
            :market,
            :class,
            :type,
            :listing_date,
            :updated_at
        )
        ON CONFLICT(symbol, market) DO UPDATE SET
          name         = excluded.name,
          class        = excluded.class,
          type         = excluded.type,
          listing_date = COALESCE(excluded.listing_date, symbol_index.listing_date),
          updated_at   = excluded.updated_at;
        """

        now = datetime.now().isoformat()
        prepared: List[Dict[str, Any]] = []

        for row in rows:
            if not isinstance(row, dict):
                raise TypeError(
                    f"upsert_symbol_index expects dict rows, got {type(row).__name__}"
                )

            symbol = str(row.get("symbol") or "").strip()
            name = str(row.get("name") or "").strip()
            market = str(row.get("market") or "").strip().upper()

            if not symbol:
                raise ValueError("upsert_symbol_index: symbol is required")
            if market not in ("SH", "SZ", "BJ"):
                raise ValueError(f"upsert_symbol_index: invalid market={market!r}")
            if not name:
                raise ValueError("upsert_symbol_index: name is required")

            listing_date = row.get("listing_date")
            if listing_date in ("", None):
                listing_date = None
            else:
                try:
                    listing_date = int(listing_date)
                except Exception:
                    listing_date = None

            prepared.append({
                "symbol": symbol,
                "name": name,
                "market": market,
                "class": row.get("class"),
                "type": row.get("type"),
                "listing_date": listing_date,
                "updated_at": now,
            })

        cur.executemany(sql, prepared)
        conn.commit()
        return cur.rowcount


def select_symbol_index(
    symbol: Optional[str] = None,
    market: Optional[str] = None,
    type_filter: Optional[str] = None,
    market_filter: Optional[str] = None,
    class_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    查询标的索引（联合主键版）

    过滤维度：
      - symbol: 精确匹配代码
      - market: 精确匹配市场
      - type_filter: 细分类
      - market_filter: 市场（与 market 二选一即可，保留兼容调用语义）
      - class_filter: 大类
    """
    conn = get_conn()
    cur = conn.cursor()

    where_clauses = []
    params: List[Any] = []

    if symbol:
        where_clauses.append("symbol = ?")
        params.append(symbol)

    actual_market = market if market is not None else market_filter
    if actual_market:
        where_clauses.append("market = ?")
        params.append(str(actual_market).strip().upper())

    if type_filter:
        where_clauses.append("type = ?")
        params.append(type_filter)

    if class_filter:
        where_clauses.append("class = ?")
        params.append(class_filter)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    sql = f"""
    SELECT
        symbol,
        name,
        market,
        class,
        type,
        listing_date,
        updated_at
    FROM symbol_index
    WHERE {where_sql}
    ORDER BY market ASC, symbol ASC;
    """

    cur.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_listing_date(symbol: str, market: str) -> Optional[int]:
    """
    获取指定标的（symbol + market）的上市日期。

    Returns:
        Optional[int]: 上市日期（YYYYMMDD），不存在则返回 None
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT listing_date FROM symbol_index WHERE symbol=? AND market=?;",
        (symbol, str(market).strip().upper()),
    )
    result = cur.fetchone()
    return result[0] if result and result[0] else None


# ==============================================================================
# symbol_profile 表操作
# ==============================================================================

def upsert_symbol_profile(profiles: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新标的档案（新字段版）。

    字段语义：
      - symbol       (str):   必需
      - total_shares (float): 总股本/总份额（万股/万份，两位小数）
      - float_shares (float): 流通股本/总份额（万股/万份，两位小数）
      - total_value  (float): 总市值（亿元，两位小数）
      - nego_value   (float): 流通市值（亿元，两位小数）
      - pe_static    (float): 静态市盈率（倍，两位小数）
      - industry     (str):   行业名称
      - region       (str):   地区（省级）
      - concepts     (list/str/None): 概念标签列表，内部 JSON 字符串存储
      - updated_at   (str):   更新时间（ISO8601）

    规则：
      - 对于无来源的字段，上游应传入 None；本函数不再进行任何推断或填充。
      - concepts 若为 list，则转为 JSON 字符串存储；若为 None/空串则存 NULL。

    Args:
        profiles: 字典列表

    Returns:
        int: 影响的行数
    """
    if not profiles:
        return 0

    conn = get_conn()
    cur = conn.cursor()

    sql = """
    INSERT INTO symbol_profile (
        symbol,
        total_shares,
        float_shares,
        total_value,
        nego_value,
        pe_static,
        industry,
        region,
        concepts,
        updated_at
    )
    VALUES (
        :symbol,
        :total_shares,
        :float_shares,
        :total_value,
        :nego_value,
        :pe_static,
        :industry,
        :region,
        :concepts,
        :updated_at
    )
    ON CONFLICT(symbol) DO UPDATE SET
        total_shares = COALESCE(excluded.total_shares, symbol_profile.total_shares),
        float_shares = COALESCE(excluded.float_shares, symbol_profile.float_shares),
        total_value  = COALESCE(excluded.total_value,  symbol_profile.total_value),
        nego_value   = COALESCE(excluded.nego_value,   symbol_profile.nego_value),
        pe_static    = COALESCE(excluded.pe_static,    symbol_profile.pe_static),
        industry     = COALESCE(excluded.industry,     symbol_profile.industry),
        region       = COALESCE(excluded.region,       symbol_profile.region),
        concepts     = COALESCE(excluded.concepts,     symbol_profile.concepts),
        updated_at   = excluded.updated_at;
    """

    now = datetime.now().isoformat()
    prepared: List[Dict[str, Any]] = []

    for p in profiles:
        if not isinstance(p, dict):
            raise TypeError(
                f"upsert_symbol_profile expects dict profiles, got {type(p).__name__}"
            )

        record: Dict[str, Any] = {
            "symbol": p.get("symbol"),
            "total_shares": p.get("total_shares"),
            "float_shares": p.get("float_shares"),
            "total_value": p.get("total_value"),
            "nego_value": p.get("nego_value"),
            "pe_static": p.get("pe_static"),
            "industry": p.get("industry"),
            "region": p.get("region"),
            # updated_at：无条件覆盖为 now，忽略调用方传入的任何值
            "updated_at": now,
        }

        concepts_val = p.get("concepts")
        if isinstance(concepts_val, list):
            record["concepts"] = json.dumps(concepts_val, ensure_ascii=False)
        elif isinstance(concepts_val, str):
            record["concepts"] = concepts_val
        else:
            record["concepts"] = None

        prepared.append(record)

    cur.executemany(sql, prepared)
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

    # concepts: 如果是 JSON 字符串，解析为列表
    if result.get("concepts"):
        try:
            result["concepts"] = json.loads(result["concepts"])
        except (json.JSONDecodeError, TypeError):
            # 保持原始字符串
            pass

    return result


# ==============================================================================
# NEW: 查询 updated_at 相关方法
# ==============================================================================

def get_profile_updated_at(symbol: str) -> Optional[str]:
    """
    获取档案的最后更新时间。

    Returns:
        Optional[str]: ISO 格式时间字符串，不存在返回 None
    """
    profile = select_symbol_profile(symbol)
    return profile.get("updated_at") if profile else None
