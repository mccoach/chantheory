# backend/services/market.py
# ==============================
# 说明：行情服务（V5.0 - 纯数据返回版）
# 改动：
#   - 删除指标计算逻辑
#   - 新增 is_latest 字段
#   - 新增 latest_bar_time 字段
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd

from backend.db.candles import select_candles_raw
from backend.utils.logger import get_logger, log_event
from backend.utils.time import to_iso_string

_LOG = get_logger("market")

async def get_candles(
    symbol: str,
    freq: str,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取K线数据（纯数据返回版）
    
    职责：
      - 查询本地不复权数据
      - 判断数据完备性
      - 返回原始K线（不计算指标）
    
    Args:
        symbol: 标的代码
        freq: 频率
        trace_id: 追踪ID
    
    Returns:
        Dict: 包含 meta, candles
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
        # 本地无数据，返回空结果
        return {
            "ok": True,
            "meta": {
                "symbol": symbol,
                "freq": freq,
                "all_rows": 0,
                "is_latest": False,
                "latest_bar_time": None,
                "message": "本地暂无数据，请稍候",
                "source": "none",
                "generated_at": datetime.now().isoformat()
            },
            "candles": []
        }
    
    # 转为DataFrame
    df = pd.DataFrame(candles)
    
    # 判断数据完备性
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
        "all_rows": len(candles_list),
        "is_latest": is_latest,
        "latest_bar_time": to_iso_string(latest_ts) if latest_ts > 0 else None,
        "source": candles[0].get('source') if candles else 'unknown',
        "generated_at": datetime.now().isoformat()
    }
    
    return {
        "ok": True,
        "meta": meta,
        "candles": candles_list
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
    
    # ===== 新增：诊断日志（临时调试）=====
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
        'volume': 'v'
    }).to_dict('records')
