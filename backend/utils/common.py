# backend/utils/common.py
# ==============================
# 说明：通用小型辅助工具函数
#
# 本轮改动：
#   - 保留既有基础工具
#   - 强化 market+symbol 双键查询
#   - 新增按双键精确获取 class/type 的辅助函数
# ==============================

from __future__ import annotations
import contextlib
import io
from typing import Optional, Dict, Any, List

from backend.db import get_conn


@contextlib.contextmanager
def silence_io():
    """with 作用域内静默 stdout/stderr，避免第三方库杂乱打印。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield


def ak_symbol_with_prefix(symbol: str) -> str:
    s = (symbol or "").strip()
    if not s:
        return s
    if s.startswith("6"):
        return "sh" + s
    if s.startswith(("0", "3")):
        return "sz" + s
    if s.startswith(("8", "4", "9")):
        return "bj" + s
    return "sz" + s


def get_symbol_market_from_db(symbol: str) -> Optional[str]:
    s = (symbol or "").strip()
    if not s:
        return None

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT market FROM symbol_index WHERE symbol=? ORDER BY market ASC LIMIT 1;",
            (s,),
        )
        row = cur.fetchone()
        if row and row[0]:
            market = str(row[0]).strip().upper()
            return market or None
        return None
    except Exception:
        return None


def get_symbol_markets_from_db(symbol: str) -> List[str]:
    s = (symbol or "").strip()
    if not s:
        return []

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT market FROM symbol_index WHERE symbol=? ORDER BY market ASC;",
            (s,),
        )
        rows = cur.fetchall()
        return [
            str(r[0]).strip().upper()
            for r in rows
            if r and r[0] and str(r[0]).strip()
        ]
    except Exception:
        return []


def get_symbol_record_from_db(symbol: str, market: str) -> Optional[Dict[str, Any]]:
    s = (symbol or "").strip()
    m = (market or "").strip().upper()
    if not s or not m:
        return None

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                symbol,
                market,
                name,
                class,
                type,
                listing_date
            FROM symbol_index
            WHERE symbol=? AND market=?
            LIMIT 1;
            """,
            (s, m),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def get_symbol_class_from_db(symbol: str, market: str) -> Optional[str]:
    item = get_symbol_record_from_db(symbol=symbol, market=market)
    if not item:
        return None
    cls = str(item.get("class") or "").strip().lower()
    return cls or None


def get_symbol_type_from_db(symbol: str, market: str) -> Optional[str]:
    item = get_symbol_record_from_db(symbol=symbol, market=market)
    if not item:
        return None
    typ = str(item.get("type") or "").strip()
    return typ or None


def prefix_symbol_with_market(symbol: str) -> str:
    s = (symbol or "").strip()
    if not s:
        raise ValueError("prefix_symbol_with_market: symbol is empty")

    market = get_symbol_market_from_db(s)
    if not market:
        raise ValueError(
            f"prefix_symbol_with_market: symbol '{s}' not found in symbol_index "
            f"或 market 字段为空；请确保先完成标的列表同步再拉取相关数据。"
        )

    prefix = market.lower()
    return f"{prefix}.{s}"


def infer_symbol_type(symbol: str, cat_hint: Optional[str] = None) -> str:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT type FROM symbol_index WHERE symbol=? LIMIT 1;", (symbol,))
        r = cur.fetchone()
        if r and r[0] and str(r[0]).strip():
            return str(r[0]).strip().upper()
    except Exception:
        pass

    s = (symbol or "").strip()
    if cat_hint:
        return cat_hint

    if s.startswith(("15", "16", "50", "51", "56", "58")):
        return "ETF"

    return "A"
