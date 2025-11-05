# backend/utils/common.py
# ==============================
# 说明：通用小型辅助工具函数
# - 本模块用于存放被多个其他模块复用的、与具体业务无关的小型工具函数。
# - 修改：移除了 lazy_import_ak 函数（已在新架构中不再需要）
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
    A股代码加交易所前缀。
    
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
