# backend/db/symbols.py
# ==============================
# 说明：标的元数据表操作模块（symbol_index / symbol_profile 专项版）
#
# 当前结构：
#   - symbol_index：联合主键 (symbol, market)
#   - symbol_profile：联合主键 (symbol, market)
#
# 注意：
#   - 本轮 symbol_profile 已彻底切换为本地批量快照极简版
#   - 旧 total_shares / total_value / nego_value / pe_static 已删除
#
# 字段单位约定（symbol_profile）：
#   - float_shares : 万股 / 万份
#   - float_value  : 万元
#
# 本轮最终修复：
#   - symbol_profile 写库前，先一次性读取 symbol_index 的有效 (symbol, market) 集合；
#   - 仅对存在于 symbol_index 的记录执行批量 upsert；
#   - 不存在于 symbol_index 的记录直接跳过；
#   - 目的：避免单条孤儿记录触发外键失败，导致整批 profile 回滚。
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
# symbol_profile 表操作（联合主键极简版）
# ==============================================================================

def upsert_symbol_profile(profiles: List[Dict[str, Any]]) -> int:
    """
    批量插入或更新标的档案（联合主键极简版）。

    字段语义：
      - symbol       (str): 必需
      - market       (str): 必需，SH/SZ/BJ
      - float_shares (float): 流通股本 / 流通份额，单位：万股 / 万份
      - float_value  (float): 流通市值，单位：万元
      - industry     (str): 行业名称
      - region       (str): 地域名称
      - concepts     (list/str/None): 概念标签列表，内部 JSON 字符串存储
      - updated_at   (str): 更新时间（ISO8601）

    最终写库策略：
      - 先一次性读取 symbol_index 的有效 (symbol, market) 集合；
      - 仅对有效集合中的 profile 记录执行批量 upsert；
      - 无效记录直接跳过，不触发外键失败。
    """
    if not profiles:
        return 0

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        sql = """
        INSERT INTO symbol_profile (
            symbol,
            market,
            float_shares,
            float_value,
            industry,
            region,
            concepts,
            updated_at
        )
        VALUES (
            :symbol,
            :market,
            :float_shares,
            :float_value,
            :industry,
            :region,
            :concepts,
            :updated_at
        )
        ON CONFLICT(symbol, market) DO UPDATE SET
            float_shares = COALESCE(excluded.float_shares, symbol_profile.float_shares),
            float_value  = COALESCE(excluded.float_value,  symbol_profile.float_value),
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

            symbol = str(p.get("symbol") or "").strip()
            market = str(p.get("market") or "").strip().upper()

            if not symbol:
                raise ValueError("upsert_symbol_profile: symbol is required")
            if market not in ("SH", "SZ", "BJ"):
                raise ValueError(f"upsert_symbol_profile: invalid market={market!r}")

            record: Dict[str, Any] = {
                "symbol": symbol,
                "market": market,
                "float_shares": p.get("float_shares"),
                "float_value": p.get("float_value"),
                "industry": p.get("industry"),
                "region": p.get("region"),
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

        if not prepared:
            return 0

        # 一次性读取 symbol_index 当前有效联合键，避免逐条查询
        cur.execute("SELECT symbol, market FROM symbol_index;")
        valid_keys = {
            (str(row[0]).strip(), str(row[1]).strip().upper())
            for row in cur.fetchall()
        }

        filtered_profiles = [
            rec for rec in prepared
            if (rec["symbol"], rec["market"]) in valid_keys
        ]

        if not filtered_profiles:
            return 0

        cur.executemany(sql, filtered_profiles)
        conn.commit()
        return cur.rowcount


def select_symbol_profile(symbol: str, market: str) -> Optional[Dict[str, Any]]:
    """
    查询单个标的的详细档案（按联合主键）。
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM symbol_profile WHERE symbol=? AND market=?;",
        (symbol, str(market).strip().upper()),
    )
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


def get_profile_updated_at(symbol: str, market: str) -> Optional[str]:
    """
    获取档案的最后更新时间。
    """
    profile = select_symbol_profile(symbol, market)
    return profile.get("updated_at") if profile else None
