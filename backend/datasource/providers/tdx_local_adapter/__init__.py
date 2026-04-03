# backend/datasource/providers/tdx_local_adapter/__init__.py
# ==============================
# 通达信本地文件适配器包
#
# 当前导出：
#   - get_symbol_list_sh_tdx : 上交所标的列表（本地 shs.tnf + base.dbf）
#   - get_symbol_list_sz_tdx : 深交所标的列表（本地 szs.tnf + base.dbf）
#   - get_symbol_list_bj_tdx : 北交所标的列表（本地 bjs.tnf + base.dbf）
#   - get_profile_snapshot_tdx : 全市场档案快照（本地 tnf + base.dbf + cfg + block）
#   - get_trade_calendar_tdx : 完整自然日历（本地 needini.dat + 周六周日规则）
#   - get_gbbq_events_raw_tdx : gbbq 全量原始事件表
# ==============================

from __future__ import annotations

from .listing_tdx import (
    get_symbol_list_sh_tdx,
    get_symbol_list_sz_tdx,
    get_symbol_list_bj_tdx,
)
from .profile_tdx import get_profile_snapshot_tdx
from .calendar_tdx import get_trade_calendar_tdx
from .gbbq_tdx import get_gbbq_events_raw_tdx

__all__ = [
    "get_symbol_list_sh_tdx",
    "get_symbol_list_sz_tdx",
    "get_symbol_list_bj_tdx",
    "get_profile_snapshot_tdx",
    "get_trade_calendar_tdx",
    "get_gbbq_events_raw_tdx",
]
