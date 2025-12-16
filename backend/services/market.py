# backend/services/market.py
# ==============================
# 说明：行情服务（V6.1 - 纯读版 /api/candles + adjust 维度）
#
# 职责：
#   - 收到 /api/candles 请求后，根据 symbol/freq/adjust：
#       * 识别标的 class（stock/fund）
#       * 决定实际用于查询的 adjust（股票永远只查 'none'，基金按请求映射）
#       * 只从本地 DB 读取 K 线数据并返回
#
#   - 注意：
#       * 所有“远程拉取 + 缺口判断 + 落库”的逻辑，统一放在 Task/Job 配方
#         （current_kline/current_factors/...）中；
#       * /api/candles 不再主动触发 bars_recipes，也不再直接调用 dispatcher。
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd

from backend.db.candles import select_candles_raw
from backend.db.symbols import select_symbol_index
from backend.utils.logger import get_logger, log_event
from backend.utils.time import to_iso_string

_LOG = get_logger("market")


def _get_symbol_class(symbol: str) -> Optional[str]:
    """
    从 symbol_index 中查询标的 class（'stock'/'fund'/...），若失败返回 None。
    """
    try:
        rows = select_symbol_index(symbol=symbol)
        if not rows:
            return None
        cls = str(rows[0].get("class") or "").strip().lower()
        return cls or None
    except Exception:
        return None


async def get_candles(
    symbol: str,
    freq: str,
    adjust: str = "none",
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取K线数据（带 adjust 维度 · 纯读 DB 版）

    流程：
      1) 识别标的 class（stock/fund）
      2) 计算实际用于 DB 查询的 adjust（effective_adjust）：
           - stock: 永远为 'none'（只存/只返回不复权）
           - fund : 按请求 adjust 映射到 'none'/'qfq'/'hfq'
      3) 只从本地 DB 读取 (symbol,freq,effective_adjust) 的 K 线
      4) 返回纯数据（不计算技术指标）

    说明：
      - 若调用方希望在读取前确保数据最新，应先通过
        POST /api/ensure-data + type='current_kline' 触发同步任务，
        等 task_done 后再调用本函数。
      - 本函数不再做任何远程拉取或缺口判断。
    """
    cls = _get_symbol_class(symbol)

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
            "freq": freq,
            "adjust": adjust,
            "class": cls,
        },
    )

    # 1) 规范化请求 adjust
    req_adj = (adjust or "none").lower().strip()
    if req_adj not in ("none", "qfq", "hfq"):
        req_adj = "none"

    # 2) 计算实际用于 DB 查询的 adjust
    if cls == "stock":
        # 股票始终只存/只查不复权数据
        eff_adjust = "none"
    else:
        # 基金/其他：按请求映射，默认为 none
        eff_adjust = req_adj

    # 3) 从本地 DB 读取
    candles = await asyncio.to_thread(
        select_candles_raw,
        symbol=symbol,
        freq=freq,
        start_ts=None,
        end_ts=None,
        limit=None,
        offset=0,
        adjust=eff_adjust,
    )

    if not candles:
        # 本地无数据，返回空结果（同步逻辑由 Task/Job 负责）
        return {
            "ok": True,
            "meta": {
                "symbol": symbol,
                "freq": freq,
                "adjust": adjust,       # 回显前端请求的 adjust
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

    # 转为DataFrame
    df = pd.DataFrame(candles)

    # 判断数据完备性（沿用原有逻辑）
    from backend.utils.time_helper import calculate_theoretical_latest_for_frontend

    latest_ts = int(candles[-1]['ts']) if candles else 0
    theoretical_ts = calculate_theoretical_latest_for_frontend(freq)
    is_latest = latest_ts >= theoretical_ts

    # 转为前端格式
    candles_list = df_to_candles_list(df)

    # 构建元数据
    meta = {
        "symbol": symbol,
        "freq": freq,
        "adjust": adjust,  # 回显前端请求的 adjust（即便 stock 只返回不复权价格）
        "class": cls,
        "all_rows": len(candles_list),
        "is_latest": is_latest,
        "latest_bar_time": to_iso_string(latest_ts) if latest_ts > 0 else None,
        "source": candles[0].get('source') if candles else 'unknown',
        "generated_at": datetime.now().isoformat(),
    }

    return {
        "ok": True,
        "meta": meta,
        "candles": candles_list,
    }


def df_to_candles_list(df: pd.DataFrame) -> list:
    """DataFrame转前端格式"""
    if df.empty:
        return []

    required_cols = ['ts', 'open', 'high', 'low', 'close', 'volume']

    for col in required_cols:
        if col not in df.columns:
            _LOG.warning(f"[格式转换] 缺少列: {col}")
            return []
    
    # 诊断日志（临时调试）
    sample_ts = df['ts'].iloc[0] if len(df) > 0 else None
    _LOG.info(
        f"[格式转换] 样本数据: "
        f"ts={sample_ts} (类型={type(sample_ts)}), "
        f"open={df['open'].iloc[0]}"
    )

    return df[required_cols].rename(columns={
        'ts': 'ts',
        'open': 'o',
        'high': 'h',
        'low': 'l',
        'close': 'c',
        'volume': 'v',
    }).to_dict('records')