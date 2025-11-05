# backend/services/market.py
# ==============================
# 说明：行情服务（V4.0 - 极简版）
# 职责：
#   1. 查询本地不复权数据
#   2. 计算指标
#   3. 全量返回（窗口截取交给前端）
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional, Set
from datetime import datetime
import pandas as pd

from backend.db.candles import select_candles_raw
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("market")

async def get_candles(
    symbol: str,
    freq: str,
    include: Optional[Set[str]] = None,
    ma_periods_map: Optional[Dict[str, int]] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取K线数据（极简版）
    
    Args:
        symbol: 标的代码
        freq: 频率
        include: 指标集合（如 {'ma', 'macd'}）
        ma_periods_map: MA周期映射（如 {'MA5': 5, 'MA10': 10}）
        trace_id: 追踪ID
    
    Returns:
        Dict: 包含 meta, candles, indicators
    """
    
    log_event(
        logger=_LOG,
        service="market",
        level="INFO",
        file=__file__,
        func="get_candles",
        line=0,
        trace_id=trace_id,
        event="get_candles.start",
        message=f"查询K线 {symbol} {freq}",
        extra={"symbol": symbol, "freq": freq}
    )
    
    # 查询本地数据（不复权）
    candles = await asyncio.to_thread(
        select_candles_raw,
        symbol=symbol,
        freq=freq
    )
    
    if not candles:
        # 本地无数据，返回空结果（让前端负责触发同步）
        return {
            "ok": True,
            "meta": {
                "symbol": symbol,
                "freq": freq,
                "all_rows": 0,
                "message": "本地暂无数据，请稍候或手动刷新",
                "source": "none",
                "generated_at": datetime.now().isoformat()
            },
            "candles": [],
            "indicators": {}
        }
    
    # 2. 转为DataFrame
    df = pd.DataFrame(candles)
    
    # 4. 计算指标（如果需要）
    indicators = {}
    if include:
        indicators = await calculate_indicators(df, include, ma_periods_map)
    
    # 5. 转为前端格式
    candles_list = df_to_candles_list(df)
    
    # 6. 构建元数据
    meta = {
        "symbol": symbol,
        "freq": freq,
        "all_rows": len(candles_list),
        "source": candles[0].get('source') if candles else 'unknown',
        "generated_at": datetime.now().isoformat()
    }
    
    return {
        "ok": True,
        "meta": meta,
        "candles": candles_list,
        "indicators": indicators
    }

async def calculate_indicators(
    df: pd.DataFrame,
    include: Set[str],
    ma_periods_map: Optional[Dict[str, int]]
) -> Dict[str, Any]:
    """计算技术指标"""
    indicators = {}
    
    if 'ma' in include and ma_periods_map:
        from backend.services.indicators import ma
        ma_result = ma(df['close'], ma_periods_map)
        indicators.update(ma_result)
    
    if 'macd' in include:
        from backend.services.indicators import macd
        macd_result = macd(df['close'])
        indicators.update(macd_result)
    
    if 'kdj' in include:
        from backend.services.indicators import kdj
        kdj_result = kdj(df['high'], df['low'], df['close'])
        indicators.update(kdj_result)
    
    if 'rsi' in include:
        from backend.services.indicators import rsi
        rsi_result = rsi(df['close'])
        indicators.update(rsi_result)
    
    if 'boll' in include:
        from backend.services.indicators import boll
        boll_result = boll(df['close'])
        indicators.update(boll_result)
    
    # 转为可序列化格式
    for key, series in indicators.items():
        if isinstance(series, pd.Series):
            indicators[key] = series.tolist()
    
    return indicators

def df_to_candles_list(df: pd.DataFrame) -> list:
    """DataFrame转前端格式"""
    if df.empty:
        return []
    
    required_cols = ['ts', 'open', 'high', 'low', 'close', 'volume']
    
    for col in required_cols:
        if col not in df.columns:
            _LOG.warning(f"[格式转换] 缺少列: {col}")
            return []
    
    return df[required_cols].rename(columns={
        'ts': 'ts',
        'open': 'o',
        'high': 'h',
        'low': 'l',
        'close': 'c',
        'volume': 'v'
    }).to_dict('records')
