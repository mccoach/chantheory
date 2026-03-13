# backend/datasource/providers/szse_adapter/__init__.py
# ==============================
# 深交所数据适配器包 (SZSE)
#
# 对外统一出口：
#   - 档案与实时指标：from .profile_szse import *
#
# 说明：
#   - 旧的远程 listing 能力已删除；
#   - symbol_index / listing 已统一切换为 TDX 本地文件解析链路；
#   - 本包当前仅保留单标的档案/实时指标相关远程能力。
# ==============================

from __future__ import annotations

from .profile_szse import (
    get_stock_profile_basic_sz_szse,
    get_stock_profile_realtime_sz_szse,
)

__all__ = [
    # profile
    "get_stock_profile_basic_sz_szse",
    "get_stock_profile_realtime_sz_szse",
]
