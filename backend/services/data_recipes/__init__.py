# backend/services/data_recipes/__init__.py
# ==============================
# 数据任务配方统一出口（包级）
#
# 对外导出：
#   - run_trade_calendar
#   - run_symbol_index
#   - run_profile_snapshot
#   - run_current_kline
#   - run_factor_events_snapshot
#   - run_watchlist_update
# ==============================

from __future__ import annotations

from .trade_calendar import run_trade_calendar
from .symbol_index import run_symbol_index
from .profile_snapshot import run_profile_snapshot
from .current_kline import run_current_kline
from .factor_events_snapshot import run_factor_events_snapshot
from .watchlist_update import run_watchlist_update

__all__ = [
    "run_trade_calendar",
    "run_symbol_index",
    "run_profile_snapshot",
    "run_current_kline",
    "run_factor_events_snapshot",
    "run_watchlist_update",
]
