# backend/services/minute_archive/reader.py
# ==============================
# 分钟归档读取器
#
# 职责：
#   - 从本地 minute archive 读取全量 1m / 5m 原始数据
#   - 返回 DataFrame
#
# 设计原则：
#   - 只读
#   - 不判断缺口
#   - 不重采样
#   - 不复权
# ==============================

from __future__ import annotations

from typing import List, Dict, Any
import pandas as pd

from backend.services.minute_archive.store import resolve_minute_archive_path, read_archive_bytes
from backend.services.minute_archive.codec import decode_record_from_bytes


def read_minute_archive_df(
    *,
    market: str,
    symbol: str,
    freq: str,
) -> pd.DataFrame:
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()
    f = str(freq or "").strip()

    if f not in ("1m", "5m"):
        raise ValueError(f"unsupported minute archive freq: {freq}")

    path = resolve_minute_archive_path(
        market=m,
        symbol=s,
        freq=f,
    )
    raw = read_archive_bytes(path)
    if not raw:
        return pd.DataFrame(columns=["date", "time", "open", "high", "low", "close", "amount", "volume"])

    rows: List[Dict[str, Any]] = []
    rec_size = 32
    total = len(raw) // rec_size

    for i in range(total):
        start = i * rec_size
        rec_raw = raw[start:start + rec_size]
        if len(rec_raw) != rec_size:
            continue
        item = decode_record_from_bytes(
            rec_raw,
            market=m,
            symbol=s,
            freq=f,
        )
        rows.append({
            "date": int(item["date"]),
            "time": str(item["time"]),
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "close": float(item["close"]),
            "amount": float(item["amount"]),
            "volume": float(item["volume"]),
        })

    if not rows:
        return pd.DataFrame(columns=["date", "time", "open", "high", "low", "close", "amount", "volume"])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["date", "time"], keep="last").sort_values(["date", "time"]).reset_index(drop=True)
    return df
