# backend/datasource/providers/baostock_adapter/__init__.py
# ==============================
# Baostock 数据适配器包 (V4.0)
#
# 当前导出：
#   - get_trade_calendar_bs : 交易日历（含 is_trading_day）
#   - get_raw_adj_factors_bs: 复权因子（前/后复权一次性原始拉取）
# ==============================

from __future__ import annotations

from .calendar_bs import get_trade_calendar_bs
from .factors_bs import get_raw_adj_factors_bs

__all__ = [
    "get_trade_calendar_bs",
    "get_raw_adj_factors_bs",
]