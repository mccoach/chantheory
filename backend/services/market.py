# backend/services/market.py
# ==============================
# 说明：行情服务（V8.0 - 日线专用 DB 版 /api/candles 第一阶段）
#
# 当前阶段职责：
#   - 收到 /api/candles 请求后：
#       * 若 freq='1d'：
#           只从本地 DB 的 candles_day_raw 读取原始日线数据并返回
#       * 若 freq!='1d'：
#           当前阶段暂不由本模块提供分钟线/周月线数据
#
# 说明：
#   - 本阶段是“日线收尾优化”阶段
#   - 日线真相源已从 candles_raw 收缩为 candles_day_raw
#   - 分钟线后续将走“归档 + 实时拼接”独立链路
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd

from backend.db.candles import select_candles_day_raw
from backend.db.symbols import select_symbol_index
from backend.utils.common import get_symbol_market_from_db
from backend.utils.logger import get_logger, log_event
from backend.utils.time import to_iso_string

_LOG = get_logger("market")


def _get_symbol_class(symbol: str) -> Optional[str]:
    try:
        rows = select_symbol_index(symbol=symbol)
        if not rows:
            return None
        cls = str(rows[0].get("class") or "").strip().lower()
        return cls or None
    except Exception:
        return None


def _get_symbol_market(symbol: str) -> Optional[str]:
    try:
        return get_symbol_market_from_db(symbol)
    except Exception:
        return None


async def get_candles(
    symbol: str,
    freq: str,
    adjust: str = "none",
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取 K 线数据（第一阶段：仅日线从 DB 读取）

    说明：
      - candles_day_raw 底表只存原始不复权日线
      - adjust 当前仅回显给前端，不参与 DB 查询
      - 若调用方希望读取前确保数据最新，应先通过
        POST /api/ensure-data + type='current_kline' 触发同步任务，
        等 task.finished 后再调用本函数。
      - 本阶段仅稳定支持 freq='1d'
    """
    cls = _get_symbol_class(symbol)
    market = _get_symbol_market(symbol)
    freq_norm = str(freq or "").strip()

    log_event(
        logger=_LOG,
        service="market",
        level="INFO",
        file=__file__,
        func="get_candles",
        line=0,
        trace_id=trace_id,
        event="get_candles.start",
        message=f"查询K线 {symbol} {freq_norm} adjust={adjust}",
        extra={
            "symbol": symbol,
            "market": market,
            "freq": freq_norm,
            "adjust": adjust,
            "class": cls,
        },
    )

    if not market:
        return {
            "ok": True,
            "meta": {
                "symbol": symbol,
                "market": None,
                "freq": freq_norm,
                "adjust": adjust,
                "class": cls,
                "all_rows": 0,
                "is_latest": False,
                "latest_bar_time": None,
                "message": "无法确定标的市场，请先完成标的列表同步或明确选择市场",
                "source": "none",
                "generated_at": datetime.now().isoformat(),
            },
            "candles": [],
        }

    if freq_norm != "1d":
        return {
            "ok": True,
            "meta": {
                "symbol": symbol,
                "market": market,
                "freq": freq_norm,
                "adjust": adjust,
                "class": cls,
                "all_rows": 0,
                "is_latest": False,
                "latest_bar_time": None,
                "message": "当前阶段仅支持从本地数据库读取日线（1d）；分钟线后续将切换为归档读取链路",
                "source": "none",
                "generated_at": datetime.now().isoformat(),
            },
            "candles": [],
        }

    candles = await asyncio.to_thread(
        select_candles_day_raw,
        market=market,
        symbol=symbol,
        start_ts=None,
        end_ts=None,
        limit=None,
        offset=0,
    )

    if not candles:
        return {
            "ok": True,
            "meta": {
                "symbol": symbol,
                "market": market,
                "freq": freq_norm,
                "adjust": adjust,
                "class": cls,
                "all_rows": 0,
                "is_latest": False,
                "latest_bar_time": None,
                "message": "本地暂无可用日线数据（可能尚未同步或同步失败，请检查 Task 状态与日志）",
                "source": "none",
                "generated_at": datetime.now().isoformat(),
            },
            "candles": [],
        }

    df = pd.DataFrame(candles)

    from backend.utils.time_helper import calculate_theoretical_latest_for_frontend

    latest_ts = int(candles[-1]["ts"]) if candles else 0
    theoretical_ts = calculate_theoretical_latest_for_frontend(freq_norm)
    is_latest = latest_ts >= theoretical_ts

    candles_list = df_to_candles_list(df)

    meta = {
        "symbol": symbol,
        "market": market,
        "freq": freq_norm,
        "adjust": adjust,
        "class": cls,
        "all_rows": len(candles_list),
        "is_latest": is_latest,
        "latest_bar_time": to_iso_string(latest_ts) if latest_ts > 0 else None,
        "source": "candles_day_raw",
        "generated_at": datetime.now().isoformat(),
    }

    return {
        "ok": True,
        "meta": meta,
        "candles": candles_list,
    }


def df_to_candles_list(df: pd.DataFrame) -> list:
    """DataFrame 转前端格式"""
    if df.empty:
        return []

    required_cols = ["ts", "open", "high", "low", "close", "volume"]

    for col in required_cols:
        if col not in df.columns:
            _LOG.warning(f"[格式转换] 缺少列: {col}")
            return []

    return df[required_cols].rename(columns={
        "ts": "ts",
        "open": "o",
        "high": "h",
        "low": "l",
        "close": "c",
        "volume": "v",
    }).to_dict("records")
