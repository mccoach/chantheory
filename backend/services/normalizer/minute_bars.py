# backend/services/normalizer/minute_bars.py
# ==============================
# TDX 分钟线标准化
#
# 职责：
#   - 将 TDX .lc1 / .lc5 原始 DataFrame
#   - 标准化为 minute_archive 统一逻辑输入 records
#
# 说明：
#   - 这里只服务：
#       * .lc1 -> 1m
#       * .lc5 -> 5m
#       * 输出 archive ready records
# ==============================

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from backend.utils.logger import get_logger

_LOG = get_logger("normalizer.minute_bars")

def normalize_tdx_minute_df_to_archive_records(
    raw_df: pd.DataFrame,
    *,
    symbol: str,
    market: str,
    freq: str,
) -> List[Dict[str, Any]]:
    if raw_df is None or raw_df.empty:
        return []

    required_cols = ["date", "time", "open", "high", "low", "close", "amount", "volume"]
    missing = [c for c in required_cols if c not in raw_df.columns]
    if missing:
        raise ValueError(f"tdx minute normalize missing columns: {missing}")

    s = str(symbol or "").strip()
    m = str(market or "").strip().upper()
    f = str(freq or "").strip()

    if not s or m not in ("SH", "SZ", "BJ"):
        raise ValueError(f"invalid symbol/market for minute normalize: symbol={symbol!r}, market={market!r}")
    if f not in ("1m", "5m"):
        raise ValueError(f"invalid freq for minute normalize: {freq!r}")

    df = raw_df.copy()
    df = df.drop_duplicates(subset=["date", "time"], keep="last").sort_values(["date", "time"]).reset_index(drop=True)

    records: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        try:
            date_v = int(row.get("date"))
        except Exception:
            continue

        time_v = str(row.get("time") or "").strip()
        if not time_v or ":" not in time_v:
            continue

        try:
            open_v = float(row.get("open"))
            high_v = float(row.get("high"))
            low_v = float(row.get("low"))
            close_v = float(row.get("close"))
        except Exception:
            continue

        try:
            amount_v = float(row.get("amount")) if row.get("amount") is not None else 0.0
        except Exception:
            amount_v = 0.0

        try:
            volume_v = float(row.get("volume")) if row.get("volume") is not None else 0.0
        except Exception:
            volume_v = 0.0

        records.append({
            "market": m,
            "symbol": s,
            "freq": f,
            "date": date_v,
            "time": time_v,
            "open": open_v,
            "high": high_v,
            "low": low_v,
            "close": close_v,
            "amount": amount_v,
            "volume": volume_v,
        })

    _LOG.info(
        "[TDX_MINUTE标准化] market=%s symbol=%s freq=%s rows=%s",
        m,
        s,
        f,
        len(records),
    )

    return records