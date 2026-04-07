# backend/services/bars_recipes.py
# ==============================
# 基础原始行情保障层（正式版）
#
# 正式职责：
#   - ensure_local_day_bars
#   - ensure_local_1m_bars
#   - ensure_local_5m_bars
#   - ensure_local_factors
#
# 设计原则：
#   - 本地真相源优先
#   - 单标的运行时缓存
#   - SH/SZ 远程逐页补缺
#   - BJ 不做远程补缺，只提示缺口
#   - 原始数据统一“最终一次性落回”本地真相源
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional
import asyncio
import pandas as pd

from backend.db.candles import select_candles_day_raw, upsert_candles_day_raw
from backend.datasource.providers.tdx_remote_adapter import get_auto_routed_bars_tdx_remote
from backend.services.market_cache import get_market_cache
from backend.services.market_gap import (
    assess_day_gap,
    assess_minute_gap,
    assess_factor_state,
)
from backend.services.minute_archive import merge_and_write_minute_archive, read_minute_archive_df
from backend.services.normalizer import normalize_tdx_gbbq_adj_factors_df
from backend.db.gbbq_events import select_gbbq_events_raw
from backend.db.factors import upsert_factors
from backend.utils.logger import get_logger

_LOG = get_logger("bars_recipes")

_CATEGORY_MAP = {
    "1d": 4,
    "5m": 0,
    "1m": 8,
}


def _base_cache_freq_from_request_freq(request_freq: str) -> str:
    f = str(request_freq or "").strip()
    if f == "1m":
        return "1m"
    if f in ("5m", "15m", "30m", "60m"):
        return "5m"
    return "1d"


async def _load_day_df_from_db(market: str, code: str) -> pd.DataFrame:
    rows = await asyncio.to_thread(
        select_candles_day_raw,
        market=market,
        symbol=code,
        start_ts=None,
        end_ts=None,
        limit=None,
        offset=0,
    )
    if not rows:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume", "amount", "turnover_rate"])
    df = pd.DataFrame(rows)
    if "turnover_rate" not in df.columns:
        df["turnover_rate"] = None
    return df[["ts", "open", "high", "low", "close", "volume", "amount", "turnover_rate"]].copy()


def _normalize_remote_day_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume", "amount", "turnover_rate"])

    df = raw_df.copy()
    if "datetime" in df.columns:
        df["ts"] = pd.to_datetime(df["datetime"], errors="coerce").astype("int64") // 10**6

    if "vol" in df.columns and "volume" not in df.columns:
        df["volume"] = pd.to_numeric(df["vol"], errors="coerce")
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "turnover_rate" not in df.columns:
        df["turnover_rate"] = None

    out_cols = ["ts", "open", "high", "low", "close", "volume", "amount", "turnover_rate"]
    for col in out_cols:
        if col not in df.columns:
            df[col] = None

    df = df[out_cols].dropna(subset=["ts", "open", "high", "low", "close"]).copy()
    df["ts"] = df["ts"].astype("int64")
    df = df.drop_duplicates(subset=["ts"], keep="last").sort_values("ts").reset_index(drop=True)
    return df


def _normalize_remote_minute_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=["date", "time", "open", "high", "low", "close", "amount", "volume"])

    df = raw_df.copy()
    if "datetime" not in df.columns:
        return pd.DataFrame(columns=["date", "time", "open", "high", "low", "close", "amount", "volume"])

    dt_series = pd.to_datetime(df["datetime"], errors="coerce")
    df["date"] = dt_series.dt.strftime("%Y%m%d")
    df["time"] = dt_series.dt.strftime("%H:%M")

    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "vol" in df.columns and "volume" not in df.columns:
        df["volume"] = pd.to_numeric(df["vol"], errors="coerce")
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    out_cols = ["date", "time", "open", "high", "low", "close", "amount", "volume"]
    for col in out_cols:
        if col not in df.columns:
            df[col] = None

    df = df[out_cols].dropna(subset=["date", "time", "open", "high", "low", "close"]).copy()
    df["date"] = df["date"].astype(int)
    df["time"] = df["time"].astype(str)
    df = df.drop_duplicates(subset=["date", "time"], keep="last").sort_values(["date", "time"]).reset_index(drop=True)
    return df


def _merge_day_frames(local_df: pd.DataFrame, remote_df: pd.DataFrame) -> pd.DataFrame:
    if local_df is None or local_df.empty:
        return remote_df.copy() if remote_df is not None else pd.DataFrame()
    if remote_df is None or remote_df.empty:
        return local_df.copy()

    df = pd.concat([local_df, remote_df], axis=0, ignore_index=True)
    df = df.drop_duplicates(subset=["ts"], keep="last").sort_values("ts").reset_index(drop=True)
    return df


def _merge_minute_frames(local_df: pd.DataFrame, remote_df: pd.DataFrame) -> pd.DataFrame:
    if local_df is None or local_df.empty:
        return remote_df.copy() if remote_df is not None else pd.DataFrame()
    if remote_df is None or remote_df.empty:
        return local_df.copy()

    df = pd.concat([local_df, remote_df], axis=0, ignore_index=True)
    df = df.drop_duplicates(subset=["date", "time"], keep="last").sort_values(["date", "time"]).reset_index(drop=True)
    return df


def _hot_page_size() -> int:
    return 2


def _cold_page_size() -> int:
    return 800


async def _fetch_remote_page(
    *,
    market: str,
    code: str,
    category: int,
    start: int,
    count: int,
) -> pd.DataFrame:
    return await get_auto_routed_bars_tdx_remote(
        category=category,
        market=market,
        symbol=code,
        start=start,
        count=count,
    )


async def ensure_local_day_bars(
    *,
    market: str,
    code: str,
    refresh_interval_seconds: Optional[int],
) -> Dict[str, Any]:
    cache = get_market_cache()
    cached = cache.get(market, code, "1d")
    is_hot = cached is not None

    if cached is None:
        working_df = await _load_day_df_from_db(market, code)
        cache.put(market, code, "1d", working_df)
    else:
        working_df = cached.copy()

    page_size = _hot_page_size() if is_hot else _cold_page_size()
    category = _CATEGORY_MAP["1d"]
    start = 0
    updated = False
    remote_exhausted = False
    escalated = False

    while True:
        gap = assess_day_gap(market=market, code=code, day_df=working_df)
        if not gap["has_gap"]:
            break
        if not gap["can_continue_remote"]:
            break

        raw_page = await _fetch_remote_page(
            market=market,
            code=code,
            category=category,
            start=start,
            count=page_size,
        )
        if raw_page is None or raw_page.empty:
            remote_exhausted = True
            break

        norm_page = _normalize_remote_day_df(raw_page)
        if norm_page.empty:
            remote_exhausted = True
            break

        before_rows = len(working_df)
        working_df = _merge_day_frames(working_df, norm_page)
        if len(working_df) > before_rows:
            updated = True

        if len(norm_page) < page_size:
            remote_exhausted = True
            break

        start += page_size

        if is_hot and not escalated:
            page_size = _cold_page_size()
            escalated = True

    if updated:
        records = []
        for _, row in working_df.iterrows():
            records.append({
                "market": market,
                "symbol": code,
                "ts": int(row["ts"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]) if row["volume"] is not None else 0.0,
                "amount": float(row["amount"]) if row["amount"] is not None else None,
            })
        await asyncio.to_thread(upsert_candles_day_raw, records)
        cache.put(market, code, "1d", working_df)

    gap = assess_day_gap(market=market, code=code, day_df=working_df)
    if gap["has_gap"] and gap["remote_supported"] and remote_exhausted:
        gap["gap_message"] = "远程可用窗口已拉尽，日线仍存在缺口"

    return {
        "df": working_df,
        "updated": updated,
        "has_gap": bool(gap["has_gap"]),
        "gap_message": str(gap["gap_message"] or ""),
        "remote_supported": bool(gap["remote_supported"]),
    }


async def _write_minute_df_once(
    *,
    market: str,
    code: str,
    freq: str,
    df: pd.DataFrame,
) -> None:
    if df is None or df.empty:
        return

    records = []
    for _, row in df.iterrows():
        records.append({
            "market": market,
            "symbol": code,
            "freq": freq,
            "date": int(row["date"]),
            "time": str(row["time"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "amount": float(row["amount"]) if row["amount"] is not None else 0.0,
            "volume": float(row["volume"]) if row["volume"] is not None else 0.0,
        })

    await asyncio.to_thread(
        merge_and_write_minute_archive,
        market=market,
        symbol=code,
        freq=freq,
        records=records,
    )


async def _ensure_local_minute_bars(
    *,
    market: str,
    code: str,
    freq: str,
    refresh_interval_seconds: Optional[int],
) -> Dict[str, Any]:
    cache = get_market_cache()
    cached = cache.get(market, code, freq)
    is_hot = cached is not None

    if cached is None:
        working_df = await asyncio.to_thread(
            read_minute_archive_df,
            market=market,
            symbol=code,
            freq=freq,
        )
        cache.put(market, code, freq, working_df)
    else:
        working_df = cached.copy()

    page_size = _hot_page_size() if is_hot else _cold_page_size()
    category = _CATEGORY_MAP[freq]
    start = 0
    updated = False
    remote_exhausted = False
    escalated = False

    while True:
        gap = assess_minute_gap(market=market, code=code, freq=freq, minute_df=working_df)
        if not gap["has_gap"]:
            break
        if not gap["can_continue_remote"]:
            break

        raw_page = await _fetch_remote_page(
            market=market,
            code=code,
            category=category,
            start=start,
            count=page_size,
        )
        if raw_page is None or raw_page.empty:
            remote_exhausted = True
            break

        norm_page = _normalize_remote_minute_df(raw_page)
        if norm_page.empty:
            remote_exhausted = True
            break

        before_rows = len(working_df)
        working_df = _merge_minute_frames(working_df, norm_page)
        if len(working_df) > before_rows:
            updated = True

        if len(norm_page) < page_size:
            remote_exhausted = True
            break

        start += page_size

        if is_hot and not escalated:
            page_size = _cold_page_size()
            escalated = True

    if updated:
        await _write_minute_df_once(
            market=market,
            code=code,
            freq=freq,
            df=working_df,
        )
        cache.put(market, code, freq, working_df)

    gap = assess_minute_gap(market=market, code=code, freq=freq, minute_df=working_df)
    if gap["has_gap"] and gap["remote_supported"] and remote_exhausted:
        gap["gap_message"] = f"远程可用窗口已拉尽，{freq} 数据仍存在缺口"

    return {
        "df": working_df,
        "updated": updated,
        "has_gap": bool(gap["has_gap"]),
        "gap_message": str(gap["gap_message"] or ""),
        "remote_supported": bool(gap["remote_supported"]),
    }


async def ensure_local_1m_bars(
    *,
    market: str,
    code: str,
    refresh_interval_seconds: Optional[int],
) -> Dict[str, Any]:
    return await _ensure_local_minute_bars(
        market=market,
        code=code,
        freq="1m",
        refresh_interval_seconds=refresh_interval_seconds,
    )


async def ensure_local_5m_bars(
    *,
    market: str,
    code: str,
    refresh_interval_seconds: Optional[int],
) -> Dict[str, Any]:
    return await _ensure_local_minute_bars(
        market=market,
        code=code,
        freq="5m",
        refresh_interval_seconds=refresh_interval_seconds,
    )


async def ensure_local_factors(
    *,
    market: str,
    code: str,
    day_df: pd.DataFrame,
    request_adjust: str,
) -> Dict[str, Any]:
    factor_state = assess_factor_state(
        market=market,
        code=code,
        day_df=day_df,
        request_adjust=request_adjust,
    )

    req_adj = str(request_adjust or "none").strip().lower()
    if req_adj == "none":
        return {
            "factor_ready": False,
            "factor_complete": False,
            "message": "",
        }

    if factor_state["factor_ready"]:
        return {
            "factor_ready": True,
            "factor_complete": True,
            "message": "",
        }

    if not factor_state["can_compute"]:
        return {
            "factor_ready": False,
            "factor_complete": False,
            "message": factor_state["message"],
        }

    rows = await asyncio.to_thread(
        select_gbbq_events_raw,
        code,
        market,
        1,
    )
    gdf = pd.DataFrame(rows) if rows else pd.DataFrame()

    if gdf.empty:
        return {
            "factor_ready": False,
            "factor_complete": False,
            "message": "复权事件为空，当前返回不复权数据",
        }

    gdf = gdf.rename(columns={
        "field1": "cash_dividend_per_10",
        "field2": "rights_price",
        "field3": "bonus_share_per_10",
        "field4": "rights_share_per_10",
    })

    try:
        factor_df = normalize_tdx_gbbq_adj_factors_df(
            gdf,
            day_df,
            symbol=code,
            market=market,
        )
    except Exception as e:
        return {
            "factor_ready": False,
            "factor_complete": False,
            "message": f"复权因子计算失败：{e}",
        }

    if factor_df is None or factor_df.empty:
        return {
            "factor_ready": False,
            "factor_complete": False,
            "message": "复权因子结果为空，当前返回不复权数据",
        }

    records = []
    for _, row in factor_df.iterrows():
        records.append({
            "symbol": code,
            "date": int(row["date"]),
            "qfq_factor": float(row["qfq_factor"]),
            "hfq_factor": float(row["hfq_factor"]),
        })
    await asyncio.to_thread(upsert_factors, records)

    return {
        "factor_ready": True,
        "factor_complete": True,
        "message": "",
    }
