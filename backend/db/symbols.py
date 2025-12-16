# backend/db/symbols.py
# ==============================
# 说明：标的元数据表操作模块（新语义版）
#
# 字段设计（symbol_index）：
#   - symbol (TEXT, PK): 标的代码（不带市场前缀，如 '600000', '159001'）
#   - name   (TEXT):     标的名称（股票简称 / 基金扩展简称）
#   - market (TEXT):     市场代码：'SH' / 'SZ'
#   - class  (TEXT):     标的类型：'stock' / 'fund'
#   - type   (TEXT):     标的类别：
#                          股票：'A' / 'B' / '科创'
#                          基金：'ETF' / 'LOF' / '实时申赎货币' / '基础设施公募REITs' / 其他原始类别
#                          指数暂不纳入本次规范（后续可扩展 'index'）
#   - board  (TEXT):     交易板块：
#                          股票：'主板' / '科创板' / '创业板'
#                          基金：NULL
#   - listing_date (INT): 上市日期，YYYYMMDD 整数
#   - updated_at   (TEXT): 更新时间，ISO8601 字符串
#
# 字段设计（symbol_profile）由 db/schema.py 定义：
#   - symbol       (TEXT, PK)
#   - total_shares (REAL): 总股本/总份额，单位：万股/万份，保留两位小数
#   - float_shares (REAL): 流通股本/份额，单位：万股/万份，保留两位小数
#   - total_value  (REAL): 总市值，单位：亿元，保留两位小数
#   - nego_value   (REAL): 流通市值，单位：亿元，保留两位小数
#   - pe_static    (REAL): 静态市盈率，倍，保留两位小数
#   - industry     (TEXT): 行业名称
#   - region       (TEXT): 地区（省级）
#   - concepts     (TEXT): 概念标签 JSON 字符串
#   - updated_at   (TEXT): 更新时间，ISO8601
#
# 关键原则：
#   - 不再兼容任何“旧格式 tuple”入参；
#   - 不再在本模块内“按代码猜测 market/class/type/board”，所有含义字段必须在上游标准化阶段给出；
#   - 保持本模块职责为“纯粹的 DB upsert/select”。
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
    批量插入或更新标的索引（新语义版，仅接受字典格式）。

    约束：
      - 不再接受 tuple 形式的旧格式入参；
      - 调用方必须显式提供字段：
          symbol, name, market, class, type, board, listing_date（可为 None）, updated_at（可省略）

    Args:
        rows: 一个可迭代对象，其中每个元素都是 dict，至少包含 'symbol' 和 'name'。

    Returns:
        int: 影响的行数
    """
    # 关键修复：仅接受 dict，不再兼容旧 tuple 格式
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
            board,
            listing_date,
            updated_at
        )
        VALUES (
            :symbol,
            :name,
            :market,
            :class,
            :type,
            :board,
            :listing_date,
            :updated_at
        )
        ON CONFLICT(symbol) DO UPDATE SET
          name         = excluded.name,
          market       = excluded.market,
          class        = excluded.class,
          type         = excluded.type,
          board        = excluded.board,
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

            prepared.append({
                "symbol": row.get("symbol"),
                "name": row.get("name"),
                "market": row.get("market"),
                "class": row.get("class"),
                "type": row.get("type"),
                "board": row.get("board"),
                "listing_date": row.get("listing_date"),
                # updated_at：无条件覆盖为 now，忽略调用方传入的任何值
                "updated_at": now,
            })

        cur.executemany(sql, prepared)
        conn.commit()
        return cur.rowcount


def select_symbol_index(
    symbol: Optional[str] = None,
    type_filter: Optional[str] = None,
    market_filter: Optional[str] = None,
    class_filter: Optional[str] = None,
    board_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    查询标的索引（新语义版）。

    过滤维度：
      - symbol: 精确匹配单一标的
      - type_filter: 标的类别过滤（'A'/'B'/'科创'/'ETF'/'LOF'/...）
      - market_filter: 市场过滤（'SH'/'SZ'）
      - class_filter: 标的类型过滤（'stock'/'fund'）
      - board_filter: 交易板块过滤（'主板'/'科创板'/'创业板'）

    Returns:
        List[Dict[str, Any]]: 标的索引列表
    """
    conn = get_conn()
    cur = conn.cursor()

    where_clauses = []
    params: List[Any] = []

    if symbol:
        where_clauses.append("symbol = ?")
        params.append(symbol)

    if type_filter:
        where_clauses.append("type = ?")
        params.append(type_filter)

    if market_filter:
        where_clauses.append("market = ?")
        params.append(market_filter)

    if class_filter:
        where_clauses.append("class = ?")
        params.append(class_filter)

    if board_filter:
        where_clauses.append("board = ?")
        params.append(board_filter)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    sql = f"""
    SELECT
        symbol,
        name,
        market,
        class,
        type,
        board,
        listing_date,
        updated_at
    FROM symbol_index
    WHERE {where_sql}
    ORDER BY symbol ASC;
    """

    cur.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_listing_date(symbol: str) -> Optional[int]:
    """
    获取指定标的的上市日期，仅从 symbol_index 表查询。

    Returns:
        Optional[int]: 上市日期（YYYYMMDD），不存在则返回 None
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT listing_date FROM symbol_index WHERE symbol=?;",
        (symbol,)
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