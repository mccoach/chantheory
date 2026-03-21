# backend/datasource/providers/baostock_adapter/__init__.py
# ==============================
# Baostock 数据适配器包
#
# 当前导出：
#   - get_raw_adj_factors_bs: 复权因子（前/后复权一次性原始拉取）
#
# 说明：
#   - trade_calendar 已彻底切换为 TDX 本地完整自然日历构建
#   - 本包不再承载交易日历能力
# ==============================

from __future__ import annotations

from .factors_bs import get_raw_adj_factors_bs

__all__ = [
    "get_raw_adj_factors_bs",
]
