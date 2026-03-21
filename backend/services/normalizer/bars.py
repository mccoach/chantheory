# backend/services/normalizer/bars.py
# ==============================
# K线与因子标准化
#
# 本轮改动：
#   - 新增：normalize_tdx_day_df_to_candles_records
#   - 用于盘后数据导入 import 第一阶段：
#       * .day -> freq=1d
#       * 原始不复权
#       * 输出 candles_raw 可写入 records
#
# 本次重构：
#   - candles_raw 已补入 market
#   - candles_raw 已删除 adjust
#   - 本文件同步输出 market 维度
# ==============================

from __future__ import annotations

import pandas as pd
from typing import Optional, Any, Dict, List

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


def normalize_baostock_adj_factors_df(
    raw_df: pd.DataFrame,
    source_id: str = "baostock.get_raw_adj_factors_bs",
) -> Optional[pd.DataFrame]:
    if raw_df is None or raw_df.empty:
        return None

    df = normalize_dataframe(raw_df)
    if df is None or df.empty:
        return None

    required_cols = [
        "dividOperateDate", "foreAdjustFactor", "backAdjustFactor"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        _LOG.error(
            "[因子标准化-Baostock] 缺少必要列: %s, source_id=%s, columns=%s",
            missing,
            source_id,
            list(df.columns),
        )
        return None

    df["date"] = df["dividOperateDate"].apply(
        lambda v: parse_yyyymmdd(str(v).strip()) if pd.notna(v) else None
    )
    df = df.dropna(subset=["date"])
    df["date"] = df["date"].astype(int)

    df["qfq_factor"] = pd.to_numeric(df["foreAdjustFactor"], errors="coerce")
    df["hfq_factor"] = pd.to_numeric(df["backAdjustFactor"], errors="coerce")

    df = df.dropna(subset=["qfq_factor", "hfq_factor"], how="all")

    if df.empty:
        return None

    out = df[["date", "qfq_factor", "hfq_factor"]].drop_duplicates(
        subset=["date"]
    ).sort_values("date").reset_index(drop=True)

    _LOG.info(
        "[因子标准化-Baostock] 标准化完成: source_id=%s, rows=%d",
        source_id,
        len(out),
    )

    return out


def normalize_tdx_day_df_to_candles_records(
    raw_df: pd.DataFrame,
    *,
    symbol: str,
    market: str,
) -> List[Dict[str, Any]]:
    """
    将 .day 原始 DataFrame 标准化为 candles_raw upsert 记录。

    当前阶段固定语义：
      - .day -> freq = 1d
      - 原始不复权
      - 全量标准化，不做日期筛选

    Args:
        raw_df: 来自 load_tdx_day_df 的原始 DataFrame
        symbol: 标的代码
        market: 市场（SH/SZ/BJ）

    Returns:
        List[Dict[str, Any]]
    """
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
    source = "tdx_local.day_import"

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
            "freq": "1d",
            "ts": ts,
            "open": open_v,
            "high": high_v,
            "low": low_v,
            "close": close_v,
            "volume": volume_v,
            "amount": amount_v,
            "turnover_rate": None,
            "source": source,
        })

    _LOG.info(
        "[TDX_DAY标准化] market=%s symbol=%s rows=%s",
        m,
        s,
        len(records),
    )

    return records
