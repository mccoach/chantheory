# backend/services/resampler.py
# ==============================
# K线重采样工具
#
# 正式职责：
#   - 1d -> 1w / 1M
#   - 5m -> 15m / 30m / 60m
#
# 设计原则：
#   - 输入输出均为系统标准 bars DataFrame：
#       ts, open, high, low, close, volume, amount, turnover_rate
#   - 不跨午休粗暴拼接
#   - 不做复权
# ==============================

from __future__ import annotations

from typing import Optional
import pandas as pd

from backend.utils.logger import get_logger

_LOG = get_logger("resampler")


def _ensure_std_columns(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    for col in ("amount", "turnover_rate"):
        if col not in x.columns:
            x[col] = None
    return x


def resample_daily_to_weekly(df_daily: pd.DataFrame) -> Optional[pd.DataFrame]:
    try:
        if df_daily is None or df_daily.empty:
            return None

        df = _ensure_std_columns(df_daily)
        df["datetime"] = pd.to_datetime(df["ts"], unit="ms")
        df = df.set_index("datetime")

        grouped = df.resample("W-FRI").agg({
            "ts": "last",
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "amount": "sum",
            "turnover_rate": "mean",
        })

        grouped = grouped.dropna(subset=["close"]).reset_index(drop=True)
        return grouped[["ts", "open", "high", "low", "close", "volume", "amount", "turnover_rate"]]

    except Exception as e:
        _LOG.error("[重采样] 1d -> 1w 失败: %s", e, exc_info=True)
        return None


def resample_daily_to_monthly(df_daily: pd.DataFrame) -> Optional[pd.DataFrame]:
    try:
        if df_daily is None or df_daily.empty:
            return None

        df = _ensure_std_columns(df_daily)
        df["datetime"] = pd.to_datetime(df["ts"], unit="ms")
        df = df.set_index("datetime")

        grouped = df.resample("ME").agg({
            "ts": "last",
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "amount": "sum",
            "turnover_rate": "mean",
        })

        grouped = grouped.dropna(subset=["close"]).reset_index(drop=True)
        return grouped[["ts", "open", "high", "low", "close", "volume", "amount", "turnover_rate"]]

    except Exception as e:
        _LOG.error("[重采样] 1d -> 1M 失败: %s", e, exc_info=True)
        return None


def resample_5m_to_target(df_5m: pd.DataFrame, target_freq: str) -> Optional[pd.DataFrame]:
    """
    5m -> 15m / 30m / 60m
    """
    tf = str(target_freq or "").strip()
    if tf not in ("15m", "30m", "60m"):
        raise ValueError(f"unsupported target minute freq: {target_freq}")

    if df_5m is None or df_5m.empty:
        return None

    rule_map = {
        "15m": "15min",
        "30m": "30min",
        "60m": "60min",
    }
    rule = rule_map[tf]

    try:
        df = _ensure_std_columns(df_5m)
        df["datetime"] = pd.to_datetime(df["ts"], unit="ms")
        df["trade_date"] = df["datetime"].dt.strftime("%Y-%m-%d")
        parts = []

        for _, g in df.groupby("trade_date"):
            x = g.copy().set_index("datetime")
            agg = x.resample(rule, label="right", closed="right").agg({
                "ts": "last",
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "amount": "sum",
                "turnover_rate": "mean",
            })
            agg = agg.dropna(subset=["close"])
            parts.append(agg)

        if not parts:
            return None

        out = pd.concat(parts, axis=0).reset_index(drop=True)
        out = out.drop_duplicates(subset=["ts"], keep="last").sort_values("ts").reset_index(drop=True)
        return out[["ts", "open", "high", "low", "close", "volume", "amount", "turnover_rate"]]

    except Exception as e:
        _LOG.error("[重采样] 5m -> %s 失败: %s", tf, e, exc_info=True)
        return None


def resample_to_target(df: pd.DataFrame, request_freq: str) -> Optional[pd.DataFrame]:
    """
    统一重采样入口：
      - 1w / 1M -> 走日线重采样
      - 15m / 30m / 60m -> 走 5m 重采样
      - 其他频率 -> 原样返回
    """
    f = str(request_freq or "").strip()

    if df is None or df.empty:
        return None

    if f == "1w":
        return resample_daily_to_weekly(df)
    if f == "1M":
        return resample_daily_to_monthly(df)
    if f in ("15m", "30m", "60m"):
        return resample_5m_to_target(df, f)

    return df.copy()
