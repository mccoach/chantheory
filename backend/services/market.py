# backend/services/market.py
# ==============================
# 说明：行情服务（V7.0 - 联合键纯读版 /api/candles）
#
# 职责：
#   - 收到 /api/candles 请求后，根据 symbol/freq：
#       * 识别标的 class（stock/fund/index/...）
#       * 识别唯一 market（当前兼容模式下仍按 symbol_index 取一条）
#       * 只从本地 DB 读取原始 K 线数据并返回
#
# 本次重构：
#   - candles_raw 底表已改为：
#       (market, symbol, freq, ts)
#   - 底表不再保留 adjust 维度
#   - adjust 参数当前仅作为前端兼容回显字段，不参与底表查询
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd

from backend.db.candles import select_candles_raw
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
    获取 K 线数据（联合键纯读 DB 版）

    说明：
      - candles_raw 底表只存原始不复权K线
      - adjust 当前仅回显给前端，不参与 DB 查询
      - 若调用方希望读取前确保数据最新，应先通过
        POST /api/ensure-data + type='current_kline' 触发同步任务，
        等 task.finished 后再调用本函数。
    """
    cls = _get_symbol_class(symbol)
    market = _get_symbol_market(symbol)

    log_event(
        logger=_LOG,
        service="market",
        level="INFO",
        file=__file__,
        func="get_candles",
        line=0,
        trace_id=trace_id,
        event="get_candles.start",
        message=f"查询K线 {symbol} {freq} adjust={adjust}",
        extra={
            "symbol": symbol,
            "market": market,
            "freq": freq,
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
                "freq": freq,
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

    candles = await asyncio.to_thread(
        select_candles_raw,
        market=market,
        symbol=symbol,
        freq=freq,
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
                "freq": freq,
                "adjust": adjust,
                "class": cls,
                "all_rows": 0,
                "is_latest": False,
                "latest_bar_time": None,
                "message": "本地暂无可用数据（可能尚未同步或同步失败，请检查 Task 状态与日志）",
                "source": "none",
                "generated_at": datetime.now().isoformat(),
            },
            "candles": [],
        }

    df = pd.DataFrame(candles)

    from backend.utils.time_helper import calculate_theoretical_latest_for_frontend

    latest_ts = int(candles[-1]["ts"]) if candles else 0
    theoretical_ts = calculate_theoretical_latest_for_frontend(freq)
    is_latest = latest_ts >= theoretical_ts

    candles_list = df_to_candles_list(df)

    meta = {
        "symbol": symbol,
        "market": market,
        "freq": freq,
        "adjust": adjust,
        "class": cls,
        "all_rows": len(candles_list),
        "is_latest": is_latest,
        "latest_bar_time": to_iso_string(latest_ts) if latest_ts > 0 else None,
        "source": candles[0].get("source") if candles else "unknown",
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
