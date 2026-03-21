# backend/services/normalizer/calendar.py
# ==============================
# 交易日历标准化
#
# 新语义：
#   - 输入应为完整自然日历
#   - 不再过滤非交易日
#   - 输出完整三列：
#       date, market, is_trading_day
# ==============================

from __future__ import annotations

import pandas as pd
from typing import Optional

from backend.utils.logger import get_logger
from backend.utils.dataframe import normalize_dataframe
from backend.utils.time import parse_yyyymmdd

_LOG = get_logger("normalizer.calendar")


def normalize_trade_calendar_df(raw_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if raw_df is None or raw_df.empty:
        return None

    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        return None

    date_col = None
    for col in ["date", "calendar_date", "trade_date", "日期", "day"]:
        if col in df.columns:
            date_col = col
            break

    if not date_col:
        _LOG.error(f"[日历标准化] 未找到日期列，columns={df.columns.tolist()}")
        return None

    if "is_trading_day" not in df.columns:
        _LOG.error(f"[日历标准化] 缺少 is_trading_day 列，columns={df.columns.tolist()}")
        return None

    df["date"] = df[date_col].apply(lambda v: parse_yyyymmdd(str(v)) if pd.notna(v) else None)
    df = df.dropna(subset=["date"])
    df["date"] = df["date"].astype(int)

    if "market" in df.columns:
        df["market"] = df["market"].astype(str).str.strip().str.upper()
        df["market"] = df["market"].replace("", "CN")
    else:
        df["market"] = "CN"

    df["is_trading_day"] = pd.to_numeric(df["is_trading_day"], errors="coerce").fillna(0).astype(int)
    df["is_trading_day"] = df["is_trading_day"].apply(lambda v: 1 if int(v) == 1 else 0)

    out = df[["date", "market", "is_trading_day"]].drop_duplicates(subset=["date"], keep="last")
    out = out.sort_values("date").reset_index(drop=True)

    return out
