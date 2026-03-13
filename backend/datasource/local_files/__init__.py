# backend/datasource/local_files/__init__.py
# ==============================
# 本地文件解析能力统一出口
#
# 职责：
#   - 提供与具体业务无关的“本地文件格式解析能力”
#   - 当前包含：
#       * TDX .tnf 解析
#       * TDX base.dbf 解析
#
# 设计原则：
#   - 这里只做“文件怎么解析”
#   - 不做 listing / profile / DB / 业务分类
# ==============================

from __future__ import annotations

from .tdx_tnf import load_tnf_df
from .tdx_base_dbf import load_base_dbf_df, load_base_dbf_df_sync

__all__ = [
    "load_tnf_df",
    "load_base_dbf_df",
    "load_base_dbf_df_sync",
]
