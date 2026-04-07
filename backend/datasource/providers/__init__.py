# backend/datasource/providers/__init__.py
# ==============================
# providers 模块导出接口
#
# 正式收口：
#   - 基础数据：TDX 本地文件解析
#   - 普通行情：TDX 普通 HQ 远程
#   - 扩展行情代码暂保留，但不进入当前正式普通行情主链
# ==============================

from __future__ import annotations

from backend.datasource.providers import tdx_local_adapter
from backend.datasource.providers import tdx_remote_adapter

__all__ = [
    "tdx_local_adapter",
    "tdx_remote_adapter",
]
