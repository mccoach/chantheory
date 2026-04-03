# backend/services/normalizer/bars.py
# ==============================
# 通用 K 线标准化
#
# 职责：
#   - 将远程/本地 provider 返回的“原始 bars DataFrame”
#     统一标准化为系统通用 bars DataFrame
#
# 输出字段：
#   - ts
#   - open
#   - high
#   - low
#   - close
#   - volume
#   - amount
#   - turnover_rate
#
# 说明：
#   - 本文件只保留“通用 bars 标准化”
#   - 不再承载：
#       * TDX .day -> DB records
#       * TDX minute -> archive records
#       * 复权因子标准化
# ==============================

from __future__ import annotations

import pandas as pd
from typing import Optional, Any

from backend.utils.logger import get_logger
from backend.utils.dataframe import normalize_dataframe
from backend.utils.time import (
    parse_yyyymmdd,
    ms_at_market_close,
    ms_from_datetime_string,
    now_ms,
)

_LOG = get_logger("normalizer.bars")

def normalize_bars_df(raw_df: pd.DataFrame, source_id: str) -> Optional[pd.DataFrame]:
    if raw_df is None or raw_df.empty:
        return None

    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        return None

    field_map = {
        "日期": "date",
        "date": "date",
        "时间": "time",
        "day": "time",
        "datetime": "time",
        "开盘": "open",
        "open": "open",
        "收盘": "close",
        "close": "close",
        "最高": "high",
        "high": "high",
        "最低": "low",
        "low": "low",
        "成交量": "volume",
        "volume": "volume",
        "成交额": "amount",
        "amount": "amount",
        "换手率": "turnover_rate",
        "换手": "turnover_rate",
        "turnover": "turnover_rate",
        "turnover_rate": "turnover_rate",
    }
    rename_map = {col: field_map[col] for col in df.columns if col in field_map}
    df = df.rename(columns=rename_map)

    has_date = "date" in df.columns
    has_time = "time" in df.columns
    time_col = "time" if has_time else ("date" if has_date else None)

    if not time_col:
        _LOG.error(f"[标准化] 未找到时间列，source={source_id}, columns={df.columns.tolist()}")
        return None

    required = ["open", "high", "low", "close"]
    if not all(c in df.columns for c in required):
        _LOG.error(f"[标准化] 缺少必需字段，source={source_id}, columns={df.columns.tolist()}")
        return None

    is_minutely = has_time
    if is_minutely:
        df["ts"] = df[time_col].apply(_safe_parse_datetime)
    else:
        df["ts"] = df[time_col].apply(_safe_parse_date_to_close)
    df = df.drop(columns=[time_col], errors="ignore")

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume"] = 0.0

    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    else:
        df["amount"] = None

    if "turnover_rate" in df.columns:
        df["turnover_rate"] = pd.to_numeric(df["turnover_rate"], errors="coerce") / 100.0
    else:
        df["turnover_rate"] = None

    output_cols = [
        "ts", "open", "high", "low", "close", "volume", "amount", "turnover_rate"
    ]
    for col in output_cols:
        if col not in df.columns:
            df[col] = None

    df = df[output_cols].copy()
    df = df.drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    return df

def _safe_parse_datetime(value: Any) -> int:
    try:
        return ms_from_datetime_string(str(value))
    except Exception as e:
        _LOG.warning(f"[时间戳解析] datetime解析失败: {value}, error={e}")
        return now_ms()

def _safe_parse_date_to_close(value: Any) -> int:
    try:
        ymd = parse_yyyymmdd(str(value))
        return ms_at_market_close(ymd)
    except Exception as e:
        _LOG.error(f"[时间戳解析] 日期解析失败: {value}, error={e}")
        return now_ms()