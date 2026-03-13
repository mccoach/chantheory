# backend/datasource/providers/sse_adapter/__init__.py
# ==============================
# 上交所数据适配器包 (SSE)
#
# 对外统一出口：
#   - 档案与统计：from .profile_sse import *
#
# 说明：
#   - 旧的远程 listing 能力已删除；
#   - symbol_index / listing 已统一切换为 TDX 本地文件解析链路；
#   - 本包当前仅保留单标的档案/统计相关远程能力。
# ==============================

from __future__ import annotations

from .profile_sse import (
    get_stock_profile_basic_sh_sse,
    get_stock_profile_value_sh_sse,
    get_stock_profile_share_sh_sse,
    get_fund_profile_basic_sh_sse,
    get_fund_profile_value_sh_sse,
    get_fund_profile_share_sh_sse,
)

__all__ = [
    # profile - stock
    "get_stock_profile_basic_sh_sse",
    "get_stock_profile_value_sh_sse",
    "get_stock_profile_share_sh_sse",
    # profile - fund
    "get_fund_profile_basic_sh_sse",
    "get_fund_profile_value_sh_sse",
    "get_fund_profile_share_sh_sse",
]
