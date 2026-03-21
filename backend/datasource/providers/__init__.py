# backend/datasource/providers/__init__.py
# ==============================
# providers 模块导出接口
#
# 说明：
#   - symbol_index / profile_snapshot 主数据源已统一切换为 TDX 本地文件解析
#   - remote profile 能力已彻底删除
#   - baostock / eastmoney / sina 仍服务于 K线 / 因子 / 日历等业务
# ==============================

from __future__ import annotations

from backend.datasource.providers import baostock_adapter
from backend.datasource.providers import eastmoney_adapter
from backend.datasource.providers import sina_adapter
from backend.datasource.providers import tdx_local_adapter

__all__ = [
    "baostock_adapter",
    "eastmoney_adapter",
    "sina_adapter",
    "tdx_local_adapter",
]
