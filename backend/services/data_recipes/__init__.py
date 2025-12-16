# backend/services/data_recipes/__init__.py
# ==============================
# 数据任务配方统一出口（包级）
#
# 对外导出：
#   - run_trade_calendar
#   - run_symbol_index
#   - run_current_kline
#   - run_current_factors
#   - run_current_profile
#   - run_watchlist_update
#
# 说明：
#   - 其他模块统一从 backend.services.data_recipes 导入；
#   - 内部分任务配方按功能拆分在 calendar/symbol/kline/factors/profile/watchlist 中。
# ==============================

from __future__ import annotations

from .calendar import run_trade_calendar
from .symbol import run_symbol_index
from .kline import run_current_kline
from .factors import run_current_factors
from .profile import run_current_profile
from .watchlist import run_watchlist_update

__all__ = [
    "run_trade_calendar",
    "run_symbol_index",
    "run_current_kline",
    "run_current_factors",
    "run_current_profile",
    "run_watchlist_update",
]
