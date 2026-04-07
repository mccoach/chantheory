# backend/services/market.py
# ==============================
# 行情成品服务（正式版）
#
# 职责：
#   - 接收 /api/candles 请求
#   - 保障本地基础真相源
#   - 按需远程补缺
#   - 按需重采样
#   - 按需复权
#   - 返回前端最终可直接消费的 candles
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd

from backend.services.freq_mapper import map_request_freq
from backend.services.bars_recipes import (
    ensure_local_day_bars,
    ensure_local_1m_bars,
    ensure_local_5m_bars,
    ensure_local_factors,
)
from backend.services.resampler import resample_to_target
from backend.services.candle_adjuster import apply_adjustment
from backend.utils.common import get_symbol_record_from_db
from backend.utils.logger import get_logger, log_event
from backend.utils.time import to_iso_string
from backend.utils.time_helper import calculate_theoretical_latest_for_frontend

_LOG = get_logger("market")


async def get_candles(
    *,
    symbol: str,
    freq: str,
    adjust: str = "none",
    refresh_interval_seconds: Optional[int] = None,
    trace_id: Optional[str] = None,
    market: Optional[str] = None,
) -> Dict[str, Any]:
    code = str(symbol or "").strip()
    market_u = str(market or "").strip().upper()

    req_adjust = str(adjust or "none").strip().lower()
    if req_adjust not in ("none", "qfq", "hfq"):
        req_adjust = "none"

    item = get_symbol_record_from_db(symbol=code, market=market_u) if code and market_u else None

    log_event(
        logger=_LOG,
        service="market",
        level="INFO",
        file=__file__,
        func="get_candles",
        line=0,
        trace_id=trace_id,
        event="get_candles.start",
        message="get_candles start",
        extra={
            "symbol": code,
            "market": market_u,
            "freq": freq,
            "adjust": req_adjust,
            "refresh_interval_seconds": refresh_interval_seconds,
        },
    )

    if not code or not market_u:
        return {
            "ok": True,
            "meta": {
                "symbol": code,
                "market": market_u or None,
                "freq": str(freq or "").strip(),
                "adjust": req_adjust,
                "actual_adjust": "none",
                "all_rows": 0,
                "is_latest": False,
                "latest_bar_time": None,
                "has_gap": True,
                "gap_message": "缺少 market 或 code 参数",
                "source": "none",
                "generated_at": datetime.now().isoformat(),
            },
            "candles": [],
        }

    if item is None:
        return {
            "ok": True,
            "meta": {
                "symbol": code,
                "market": market_u,
                "freq": str(freq or "").strip(),
                "adjust": req_adjust,
                "actual_adjust": "none",
                "all_rows": 0,
                "is_latest": False,
                "latest_bar_time": None,
                "has_gap": True,
                "gap_message": "标的不在 symbol_index 中，请先同步标的列表",
                "source": "none",
                "generated_at": datetime.now().isoformat(),
            },
            "candles": [],
        }

    mapping = map_request_freq(freq)
    request_freq = mapping["request_freq"]

    day_result = await ensure_local_day_bars(
        market=market_u,
        code=code,
        refresh_interval_seconds=refresh_interval_seconds,
    )
    day_df = day_result["df"]

    factor_result = await ensure_local_factors(
        market=market_u,
        code=code,
        day_df=day_df,
        request_adjust=req_adjust,
    )

    base_df = day_df
    minute_gap = {"has_gap": False, "gap_message": ""}

    if mapping["need_minute"]:
        base_minute_freq = mapping["base_minute_freq"]
        if base_minute_freq == "1m":
            minute_result = await ensure_local_1m_bars(
                market=market_u,
                code=code,
                refresh_interval_seconds=refresh_interval_seconds,
            )
        else:
            minute_result = await ensure_local_5m_bars(
                market=market_u,
                code=code,
                refresh_interval_seconds=refresh_interval_seconds,
            )

        base_df = minute_result["df"]
        minute_gap = {
            "has_gap": bool(minute_result["has_gap"]),
            "gap_message": str(minute_result["gap_message"] or ""),
        }

    if mapping["need_resample"]:
        result_df = await asyncio.to_thread(resample_to_target, base_df, request_freq)
        if result_df is None:
            result_df = pd.DataFrame()
    else:
        result_df = base_df.copy() if base_df is not None else pd.DataFrame()

    adjusted_df, actual_adjust, adjust_message = await asyncio.to_thread(
        apply_adjustment,
        market=market_u,
        code=code,
        bars_df=result_df,
        request_adjust=req_adjust,
    )

    final_df = adjusted_df if adjusted_df is not None else pd.DataFrame()

    has_gap = bool(day_result["has_gap"]) or bool(minute_gap["has_gap"])
    gap_message = ""

    if minute_gap["has_gap"]:
        gap_message = minute_gap["gap_message"]
    elif day_result["has_gap"]:
        gap_message = day_result["gap_message"]

    if factor_result.get("message"):
        if gap_message:
            gap_message = f"{gap_message}；{factor_result['message']}"
        else:
            gap_message = factor_result["message"]

    if adjust_message:
        if gap_message:
            gap_message = f"{gap_message}；{adjust_message}"
        else:
            gap_message = adjust_message

    candles = _df_to_candles_list(final_df)

    latest_ts = int(final_df["ts"].iloc[-1]) if final_df is not None and not final_df.empty else 0
    theoretical_ts = calculate_theoretical_latest_for_frontend(request_freq)
    is_latest = bool(latest_ts >= theoretical_ts) if latest_ts > 0 else False

    meta = {
        "symbol": code,
        "market": market_u,
        "freq": request_freq,
        "adjust": req_adjust,
        "actual_adjust": actual_adjust,
        "all_rows": len(candles),
        "is_latest": is_latest,
        "latest_bar_time": to_iso_string(latest_ts) if latest_ts > 0 else None,
        "has_gap": has_gap,
        "gap_message": gap_message or "",
        "source": "local_truth_with_remote_gap_fill",
        "generated_at": datetime.now().isoformat(),
    }

    return {
        "ok": True,
        "meta": meta,
        "candles": candles,
    }


def _df_to_candles_list(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []

    required = ["ts", "open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            return []

    x = df.copy()
    return x[required].rename(columns={
        "open": "o",
        "high": "h",
        "low": "l",
        "close": "c",
        "volume": "v",
    }).to_dict("records")
