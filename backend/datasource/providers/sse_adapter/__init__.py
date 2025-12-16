# backend/datasource/providers/sse_adapter/__init__.py
# ==============================
# 上交所数据适配器包 (SSE)
# 对外统一出口：
#   - 标的列表：from .listing import get_stock_list_sh_sse, get_fund_list_sh_sse, get_index_list_sh_sse
#   - 档案与统计：from .profile import *
#   - 后续可以在本包内新增 bars.py / realtime.py 等模块，并在此处统一 re-export。
# ==============================

from __future__ import annotations

from .listing_sse import (
    get_stock_list_sh_sse,
    get_fund_list_sh_sse,
    get_index_list_sh_sse,
)

from .profile_sse import (
    get_stock_profile_basic_sh_sse,
    get_stock_profile_value_sh_sse,
    get_stock_profile_share_sh_sse,
    get_fund_profile_basic_sh_sse,
    get_fund_profile_value_sh_sse,
    get_fund_profile_share_sh_sse,
)

__all__ = [
    # listing
    "get_stock_list_sh_sse",
    "get_fund_list_sh_sse",
    "get_index_list_sh_sse",
    # profile - stock
    "get_stock_profile_basic_sh_sse",
    "get_stock_profile_value_sh_sse",
    "get_stock_profile_share_sh_sse",
    # profile - fund
    "get_fund_profile_basic_sh_sse",
    "get_fund_profile_value_sh_sse",
    "get_fund_profile_share_sh_sse",
]