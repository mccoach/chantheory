# backend/utils/common.py
# ==============================
# 说明：通用小型辅助工具函数
# - 本模块用于存放被多个其他模块复用的、与具体业务无关的小型工具函数。
# - 修改：
#   * 保留 ak_symbol_with_prefix（供 AkShare 适配器使用）
#   * 基于 symbol_index.market 的前缀工具：
#       - get_symbol_market_from_db     : 从 DB 读取市场信息
#       - prefix_symbol_with_market     : 按统一规则为 symbol 添加市场前缀字符串
# ==============================

from __future__ import annotations
import contextlib
import io
from typing import Optional

from backend.db import get_conn

@contextlib.contextmanager
def silence_io():
    """with 作用域内静默 stdout/stderr，避免第三方库杂乱打印。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield

def ak_symbol_with_prefix(symbol: str) -> str:
    """
    A股代码加交易所前缀（历史工具，主要供 AkShare 适配器使用）。

    规则:
    - '6' 开头 → 'sh' (上交所主板)
    - '0'/'3' 开头 → 'sz' (深交所主板/创业板)
    - '8'/'4' 开头 → 'bj' (北交所)
    - 其他 → 默认 'sz'
    
    Args:
        symbol (str): 不带前缀的股票代码，如 '000001'
    
    Returns:
        str: 带前缀的代码，如 'sz000001'
    """
    s = (symbol or "").strip()
    if not s:
        return s
    if s.startswith("6"):
        return "sh" + s
    if s.startswith(("0", "3")):
        return "sz" + s
    if s.startswith(("8", "4")):
        return "bj" + s
    return "sz" + s  # 默认深证

def get_symbol_market_from_db(symbol: str) -> Optional[str]:
    """
    从 symbol_index 表中查询指定 symbol 的 market 字段。

    语义：
      - 返回大写市场代码：'SH' / 'SZ' / 'BJ' / ...；
      - 未找到或查询失败时返回 None。

    注意：
      - 这是整个系统中“市场归属”的唯一权威来源；
      - 所有需要根据 symbol 判定市场的逻辑，应优先经由此函数。
    """
    s = (symbol or "").strip()
    if not s:
        return None

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT market FROM symbol_index WHERE symbol=? LIMIT 1;",
            (s,),
        )
        row = cur.fetchone()
        if row and row[0]:
            market = str(row[0]).strip().upper()
            return market or None
        return None
    except Exception:
        # 查询失败时不抛出，让上层决定如何处理
        return None

def prefix_symbol_with_market(symbol: str) -> str:
    """
    使用 symbol_index 中的市场信息，为内部 symbol 添加统一格式的“市场前缀”。

    本质动作：
      - 读取系统内对该 symbol 的市场归属（symbol_index.market）；
      - 将 market 转为小写前缀，并与 symbol 组合成一个“带前缀的代码字符串”。

    当前格式规则：
      - 'SH' + '600000' → 'sh.600000'
      - 'SZ' + '000001' → 'sz.000001'
      - 'BJ' + '430047' → 'bj.430047'  （如有）

    Args:
        symbol: 不带前缀的股票代码，如 '600000'

    Returns:
        str: 带市场前缀的代码字符串，如 'sh.600000'

    Raises:
        ValueError: 当 symbol 为空或 symbol_index 中无对应记录时。
    """
    s = (symbol or "").strip()
    if not s:
        raise ValueError("prefix_symbol_with_market: symbol is empty")

    market = get_symbol_market_from_db(s)
    if not market:
        raise ValueError(
            f"prefix_symbol_with_market: symbol '{s}' not found in symbol_index "
            f"或 market 字段为空；请确保先完成标的列表同步再拉取相关数据。"
        )

    prefix = market.lower()  # 'SH' → 'sh'
    return f"{prefix}.{s}"

def infer_symbol_type(symbol: str, cat_hint: Optional[str] = None) -> str:
    """
    推断标的品类：优先使用`symbol_index`表，否则按代码前缀弱推断。
    
    Args:
        symbol (str): 标的代码
        cat_hint (Optional[str]): 可选的类别提示，如 'A', 'ETF', 'LOF'
    
    Returns:
        str: 标的类型，如 'A', 'ETF', 'LOF'
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT type FROM symbol_index WHERE symbol=? LIMIT 1;", (symbol,))
        r = cur.fetchone()
        if r and r[0] and str(r[0]).strip():
            return str(r[0]).strip().upper()
    except Exception:
        pass
    
    # 数据库未命中或查询失败，使用前缀推断
    s = (symbol or "").strip()
    if cat_hint:
        return cat_hint

    # 常见ETF/LOF前缀
    if s.startswith(("15", "16", "50", "51", "56", "58")):
        return "ETF"
    
    return "A"  # 默认A股
