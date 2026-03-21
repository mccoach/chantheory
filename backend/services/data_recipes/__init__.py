# backend/services/data_recipes/__init__.py
# ==============================
# 数据任务配方统一出口（包级）
#
# 对外导出：
#   - run_trade_calendar
#   - run_symbol_index
#   - run_profile_snapshot
#   - run_current_kline
#   - run_current_factors
#   - run_watchlist_update
#
# 说明：
#   - current_profile 已彻底删除
# ==============================

from __future__ import annotations

from .calendar import run_trade_calendar
from .symbol import run_symbol_index
from .profile_snapshot import run_profile_snapshot
from .kline import run_current_kline
from .factors import run_current_factors
from .watchlist import run_watchlist_update

__all__ = [
    "run_trade_calendar",
    "run_symbol_index",
    "run_profile_snapshot",
    "run_current_kline",
    "run_current_factors",
    "run_watchlist_update",
]
