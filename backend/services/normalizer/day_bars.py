# backend/services/normalizer/day_bars.py
# ==============================
# TDX 日线标准化
#
# 职责：
#   - 将 TDX .day 原始 DataFrame
#   - 标准化为 candles_day_raw 可写入 records
#
# 说明：
#   - 这里只服务：
#       * .day -> 1d
#       * 原始不复权
#       * 输出 DB ready records
# ==============================

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from backend.utils.logger import get_logger
from backend.utils.time import ms_at_market_close

_LOG = get_logger("normalizer.day_bars")

def normalize_tdx_day_df_to_candles_records(
    raw_df: pd.DataFrame,
    *,
    symbol: str,
    market: str,
) -> List[Dict[str, Any]]:
    if raw_df is None or raw_df.empty:
        return []

    required_cols = ["date", "open", "high", "low", "close", "amount", "volume"]
    missing = [c for c in required_cols if c not in raw_df.columns]
    if missing:
        raise ValueError(f"tdx day normalize missing columns: {missing}")

    s = str(symbol or "").strip()
    m = str(market or "").strip().upper()
    if not s or m not in ("SH", "SZ", "BJ"):
        raise ValueError(f"invalid symbol/market for day normalize: symbol={symbol!r}, market={market!r}")

    df = raw_df.copy()
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)

    records: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        date_val = row.get("date")
        if date_val is None:
            continue

        try:
            ymd = int(date_val)
        except Exception:
            continue

        if not (19000101 <= ymd <= 21001231):
            continue

        ts = ms_at_market_close(ymd)

        try:
            open_v = float(row.get("open"))
            high_v = float(row.get("high"))
            low_v = float(row.get("low"))
            close_v = float(row.get("close"))
        except Exception:
            continue

        try:
            volume_v = float(row.get("volume")) if row.get("volume") is not None else 0.0
        except Exception:
            volume_v = 0.0

        try:
            amount_v = float(row.get("amount")) if row.get("amount") is not None else None
        except Exception:
            amount_v = None

        records.append({
            "market": m,
            "symbol": s,
            "ts": ts,
            "open": open_v,
            "high": high_v,
            "low": low_v,
            "close": close_v,
            "volume": volume_v,
            "amount": amount_v,
        })

    _LOG.info(
        "[TDX_DAY标准化] market=%s symbol=%s rows=%s",
        m,
        s,
        len(records),
    )

    return records