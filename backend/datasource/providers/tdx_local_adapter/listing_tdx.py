# backend/datasource/providers/tdx_local_adapter/listing_tdx.py
# ==============================
# 通达信本地文件适配器 - 标的列表
#
# 职责：
#   1. 调用本地文件解析层：
#       - .tnf 解析
#       - base.dbf 解析
#   2. 在 provider 层完成“标的列表原始表”的组装：
#       - tnf + base.dbf(listing_date)
#   3. 返回统一原始 DataFrame
#
# 明确不做：
#   - 不写 DB
#   - 不做 class/type 业务分类
#   - 不发 SSE
#   - 不参与 symbol_profile 业务落库
#
# 分层原则：
#   - local_files 层：只负责“文件格式怎么解析”
#   - 本 provider：负责“TDX 本地数据源如何组装成 listing 原始表”
# ==============================

from __future__ import annotations

import asyncio
from typing import Optional

import pandas as pd

from backend.datasource.local_files import load_tnf_df, load_base_dbf_df_sync
from backend.utils.logger import get_logger

_LOG = get_logger("tdx_local_adapter")


def _merge_listing_date(df_tnf: pd.DataFrame, df_base: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df_tnf is None or df_tnf.empty:
        return pd.DataFrame()

    df = df_tnf.copy()

    if df_base is None or df_base.empty:
        df["listing_date"] = None
        return df

    merged = df.merge(
        df_base[["symbol", "market", "listing_date"]],
        on=["symbol", "market"],
        how="left",
    )

    # merge 后再次强制 object，杜绝 pandas 自动浮点化
    if "listing_date" in merged.columns:
        merged["listing_date"] = merged["listing_date"].astype("object")

    return merged


def _build_symbol_list_df_sync(market: str) -> pd.DataFrame:
    """
    同步构建某市场的统一原始 DataFrame：
      tnf + base.dbf(listing_date)
    """
    df_tnf = load_tnf_df(market)
    df_base = load_base_dbf_df_sync()
    return _merge_listing_date(df_tnf, df_base)


async def get_symbol_list_sh_tdx() -> pd.DataFrame:
    return await asyncio.to_thread(_build_symbol_list_df_sync, "SH")


async def get_symbol_list_sz_tdx() -> pd.DataFrame:
    return await asyncio.to_thread(_build_symbol_list_df_sync, "SZ")


async def get_symbol_list_bj_tdx() -> pd.DataFrame:
    return await asyncio.to_thread(_build_symbol_list_df_sync, "BJ")
