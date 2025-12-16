# backend/datasource/providers/szse_adapter/__init__.py
# ==============================
# 深交所数据适配器包 (SZSE)
# 对外统一出口：
#   - 标的列表：from .listing import get_stock_list_sz_szse, get_fund_list_sz_szse, get_index_list_sz_szse
#   - 档案与实时指标：from .profile import *
# ==============================

from __future__ import annotations

from .listing_szse import (
    get_stock_list_sz_szse,
    get_fund_list_sz_szse,
    get_index_list_sz_szse,
)

from .profile_szse import (
    get_stock_profile_basic_sz_szse,
    get_stock_profile_realtime_sz_szse,
)

__all__ = [
    # listing
    "get_stock_list_sz_szse",
    "get_fund_list_sz_szse",
    "get_index_list_sz_szse",
    # profile
    "get_stock_profile_basic_sz_szse",
    "get_stock_profile_realtime_sz_szse",
]