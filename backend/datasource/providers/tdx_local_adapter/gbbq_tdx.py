# backend/datasource/providers/tdx_local_adapter/gbbq_tdx.py
# ==============================
# 通达信本地文件适配器 - gbbq 全量原始事件表
#
# 职责：
#   1. 调用本地文件解析层：
#       - gbbq
#   2. 在 provider 层完成“全量原始事件表”的最小组装
#   3. 返回统一原始 DataFrame
#
# 输出字段：
#   - market
#   - symbol
#   - date
#   - category
#   - field1
#   - field2
#   - field3
#   - field4
#
# 明确不做：
#   - 不过滤 category
#   - 不做业务解释
#   - 不写 DB
# ==============================

from __future__ import annotations

import asyncio
import pandas as pd

from backend.datasource.local_files import load_tdx_gbbq_df
from backend.utils.logger import get_logger

_LOG = get_logger("tdx_local_adapter.gbbq")


def _build_gbbq_events_raw_df_sync() -> pd.DataFrame:
    df = load_tdx_gbbq_df()
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "market",
            "symbol",
            "date",
            "category",
            "field1",
            "field2",
            "field3",
            "field4",
        ])

    out = df[[
        "market",
        "symbol",
        "date",
        "category",
        "field1",
        "field2",
        "field3",
        "field4",
    ]].copy()

    out["market"] = out["market"].astype(str).str.strip().str.upper()
    out["symbol"] = out["symbol"].astype(str).str.strip()

    out = out.drop_duplicates(subset=["market", "symbol", "date", "category"], keep="last")
    out = out.sort_values(["market", "symbol", "date", "category"]).reset_index(drop=True)

    _LOG.info("[TDX][GBBQ_EVENTS_RAW] rows=%s", len(out))
    return out


async def get_gbbq_events_raw_tdx() -> pd.DataFrame:
    return await asyncio.to_thread(_build_gbbq_events_raw_df_sync)
