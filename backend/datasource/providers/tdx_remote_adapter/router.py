# backend/datasource/providers/tdx_remote_adapter/router.py
# ==============================
# TDX 远程 bars 调用路由决策
#
# 职责：
#   - 根据本地 symbol_index 中的 class/type
#   - 决定某标的优先走：
#       * security_bars
#       * index_bars
#
# 当前阶段原则：
#   - 指数 -> index_bars
#   - 其余全部先走 security_bars
#   - 后续可根据实测结果继续收口，但职责仍应留在本模块
# ==============================

from __future__ import annotations

from typing import Literal, Optional

from backend.db.symbols import select_symbol_index

RouteKind = Literal["security_bars", "index_bars"]

def decide_tdx_bars_route(
    *,
    symbol: str,
    market: str,
) -> RouteKind:
    s = str(symbol or "").strip()
    m = str(market or "").strip().upper()
    if not s or m not in ("SH", "SZ", "BJ"):
        raise ValueError(f"invalid symbol/market for tdx bars route: {symbol} {market}")

    rows = select_symbol_index(symbol=s, market=m)
    if not rows:
        # 没有本地 metadata 时，当前阶段默认先走 security_bars
        return "security_bars"

    item = rows[0]
    cls = str(item.get("class") or "").strip().lower()

    if cls == "index":
        return "index_bars"

    return "security_bars"