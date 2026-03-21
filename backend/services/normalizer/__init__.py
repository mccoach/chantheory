# backend/services/normalizer/__init__.py
# ==============================
# normalizer 包统一出口
#
# 当前包含：
#   - bars
#   - calendar
#   - symbols
#   - profile
#
# 本轮新增：
#   - normalize_tdx_day_df_to_candles_records
# ==============================

from __future__ import annotations

from .bars import (
    normalize_bars_df,
    normalize_baostock_adj_factors_df,
    normalize_tdx_day_df_to_candles_records,
)
from .calendar import normalize_trade_calendar_df
from .symbols import normalize_symbol_list_df
from .profile import normalize_profile_snapshot_df

__all__ = [
    "normalize_bars_df",
    "normalize_baostock_adj_factors_df",
    "normalize_tdx_day_df_to_candles_records",
    "normalize_trade_calendar_df",
    "normalize_symbol_list_df",
    "normalize_profile_snapshot_df",
]
