# backend/datasource/providers/__init__.py
# ==============================
# providers 模块导出接口（V2.0 - 去除 akshare 直接依赖）
#
# 说明：
#   - 不再在模块导入阶段加载 akshare_adapter，以便后续完全卸载 akshare 库。
#   - 当前对外仅导出：
#       * sse_adapter
#       * szse_adapter
#       * baostock_adapter
#       * eastmoney_adapter
#       * sina_adapter
# ==============================

from __future__ import annotations

from backend.datasource.providers import sse_adapter
from backend.datasource.providers import szse_adapter
from backend.datasource.providers import baostock_adapter
from backend.datasource.providers import eastmoney_adapter
from backend.datasource.providers import sina_adapter

__all__ = [
    "sse_adapter",
    "szse_adapter",
    "baostock_adapter",
    "eastmoney_adapter",
    "sina_adapter",
]