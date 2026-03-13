# backend/datasource/providers/tdx_local_adapter/__init__.py
# ==============================
# 通达信本地文件适配器包
#
# 当前导出：
#   - get_symbol_list_sh_tdx : 上交所标的列表（本地 shs.tnf + base.dbf）
#   - get_symbol_list_sz_tdx : 深交所标的列表（本地 szs.tnf + base.dbf）
#   - get_symbol_list_bj_tdx : 北交所标的列表（本地 bjs.tnf + base.dbf）
#
# 说明：
#   - 本包属于 provider 层，对外暴露“TDX 本地数据源如何形成 listing 原始表”
#   - 更底层的文件格式解析能力已下沉到 backend.datasource.local_files
# ==============================

from __future__ import annotations

from .listing_tdx import (
    get_symbol_list_sh_tdx,
    get_symbol_list_sz_tdx,
    get_symbol_list_bj_tdx,
)

__all__ = [
    "get_symbol_list_sh_tdx",
    "get_symbol_list_sz_tdx",
    "get_symbol_list_bj_tdx",
]
