# backend/services/normalizer/__init__.py
# ==============================
# normalizer 包统一出口
#
# 最终结构：
#   - bars.py        : 通用 bars 标准化
#   - day_bars.py    : TDX .day -> DB records
#   - minute_bars.py : TDX minute -> archive records
#   - factors.py     : 复权因子标准化
#   - calendar.py
#   - symbols.py
#   - profile.py
# ==============================

from __future__ import annotations

from .bars import normalize_bars_df
from .day_bars import normalize_tdx_day_df_to_candles_records
from .minute_bars import normalize_tdx_minute_df_to_archive_records
from .factors import normalize_tdx_gbbq_adj_factors_df
from .calendar import normalize_trade_calendar_df
from .symbols import normalize_symbol_list_df
from .profile import normalize_profile_snapshot_df

__all__ = [
    "normalize_bars_df",
    "normalize_tdx_day_df_to_candles_records",
    "normalize_tdx_minute_df_to_archive_records",
    "normalize_tdx_gbbq_adj_factors_df",
    "normalize_trade_calendar_df",
    "normalize_symbol_list_df",
    "normalize_profile_snapshot_df",
]
