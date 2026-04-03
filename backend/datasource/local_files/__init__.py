# backend/datasource/local_files/__init__.py
# ==============================
# 本地文件解析能力统一出口
#
# 职责：
#   - 提供与具体业务无关的“本地文件格式解析能力”
#   - 当前包含：
#       * TDX .tnf 解析
#       * TDX base.dbf 解析
#       * TDX tdxhy.cfg 解析
#       * TDX tdxzs3.cfg 解析
#       * TDX infoharbor_block.dat 解析
#       * TDX needini.dat 解析
#       * TDX .day 解析
#       * TDX .lc1 / .lc5 解析
#       * TDX gbbq 解析
#
# 设计原则：
#   - 这里只做“文件怎么解析”
#   - 不做 listing / profile / calendar / import orchestration / DB / 业务分类
# ==============================

from __future__ import annotations

from .tdx_tnf import load_tnf_df
from .tdx_base_dbf import load_base_dbf_df, load_base_dbf_df_sync
from .tdxhy_cfg import load_tdxhy_cfg_df
from .tdxzs3_cfg import load_tdxzs3_cfg_df
from .infoharbor_block_dat import load_infoharbor_block_df
from .needini_dat import load_needini_holidays_df, get_needini_latest_year
from .tdx_day import load_tdx_day_df
from .tdx_minute import load_tdx_minute_df
from .tdx_gbbq import load_tdx_gbbq_df

__all__ = [
    "load_tnf_df",
    "load_base_dbf_df",
    "load_base_dbf_df_sync",
    "load_tdxhy_cfg_df",
    "load_tdxzs3_cfg_df",
    "load_infoharbor_block_df",
    "load_needini_holidays_df",
    "get_needini_latest_year",
    "load_tdx_day_df",
    "load_tdx_minute_df",
    "load_tdx_gbbq_df",
]
