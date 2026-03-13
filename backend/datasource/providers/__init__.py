# backend/datasource/providers/__init__.py
# ==============================
# providers 模块导出接口
#
# 说明：
#   - listing / symbol_index 主数据源已统一切换为 TDX 本地文件解析（tdx_local_adapter）
#   - SSE / SZSE 保留其单标的远程能力（档案/统计等）
#   - 其他 provider（baostock/eastmoney/sina）仍服务于 K线 / 因子 / 日历等业务
# ==============================

from __future__ import annotations

from backend.datasource.providers import sse_adapter
from backend.datasource.providers import szse_adapter
from backend.datasource.providers import baostock_adapter
from backend.datasource.providers import eastmoney_adapter
from backend.datasource.providers import sina_adapter
from backend.datasource.providers import tdx_local_adapter

__all__ = [
    "sse_adapter",
    "szse_adapter",
    "baostock_adapter",
    "eastmoney_adapter",
    "sina_adapter",
    "tdx_local_adapter",
]
