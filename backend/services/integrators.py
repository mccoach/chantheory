# backend/services/integrators.py
# ==============================
# 说明: 复合数据集成器 (The Integrator - 全异步版)
# - 职责: 编排 `dispatcher` 和 `normalizer` 以完成复杂数据任务。
# - 核心优势: 使用 asyncio.gather 并发执行多个数据获取任务，充分发挥异步性能优势。
# ==============================

from __future__ import annotations
import asyncio
from typing import Dict, Any, Optional
import pandas as pd

from backend.datasource import dispatcher
from backend.services import normalizer
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("services.integrator")

async def get_daily_bars_with_factors(
    symbol: str, 
    start_date: str, 
    end_date: str
) -> Optional[Dict[str, pd.DataFrame]]:
    """
    获取A股的标准化日线数据及标准化的复权因子。
    使用 asyncio.gather 并发执行三次数据获取，提高效率。
    """
    log_event(
        logger=_LOG, service="integrator", level="INFO",
        event="integrate.start", message=f"Integrating daily bars and factors for {symbol}",
        extra={"symbol": symbol, "start": start_date, "end": end_date},
        file=__file__, func="get_daily_bars_with_factors", line=0, trace_id=None
    )

    # --- 并发执行三次数据调度 (异步的核心优势) ---
    results = await asyncio.gather(
        dispatcher.fetch('stock_bars', symbol=symbol, start_date=start_date, end_date=end_date, period='daily', adjust=''),
        dispatcher.fetch('adj_factor', symbol=symbol, adjust_type='qfq-factor'),
        dispatcher.fetch('adj_factor', symbol=symbol, adjust_type='hfq-factor'),
        return_exceptions=True
    )
    
    # 解包结果
    raw_bars_df, bars_source_id = results[0] if not isinstance(results[0], Exception) else (None, None)
    raw_qfq_df, qfq_source_id = results[1] if not isinstance(results[1], Exception) else (None, None)
    raw_hfq_df, hfq_source_id = results[2] if not isinstance(results[2], Exception) else (None, None)

    # --- K线数据标准化 ---
    df_bars = normalizer.normalize_bars_df(raw_bars_df, bars_source_id)
    if df_bars is None or df_bars.empty:
        log_event(
            logger=_LOG, service="integrator", level="ERROR",
            event="integrate.fail", message=f"Failed to get or normalize bars for {symbol}",
            file=__file__, func="get_daily_bars_with_factors", line=0, trace_id=None
        )
        return None

    # --- 复权因子标准化与整合 ---
    df_qfq = normalizer.normalize_adj_factors_df(raw_qfq_df, qfq_source_id)
    df_hfq = normalizer.normalize_adj_factors_df(raw_hfq_df, hfq_source_id)

    if df_qfq is None or df_hfq is None:
        log_event(
            logger=_LOG, service="integrator", level="WARN",
            event="integrate.no_factors", message=f"Could not retrieve factors for {symbol}",
            file=__file__, func="get_daily_bars_with_factors", line=0, trace_id=None
        )
        empty_factors = pd.DataFrame(columns=['symbol', 'date', 'qfq_factor', 'hfq_factor'])
        return {'bars': df_bars, 'factors': empty_factors}

    # 合并因子
    df_factors = pd.merge(
        df_qfq.rename(columns={'factor': 'qfq_factor'}),
        df_hfq.rename(columns={'factor': 'hfq_factor'}),
        on='date', how='outer'
    )

    # 创建完整的日期范围（基于K线数据）
    all_dates = pd.to_datetime(df_bars['ts'], unit='ms').dt.strftime('%Y%m%d').astype(int).unique()
    date_range_df = pd.DataFrame({'date': sorted(all_dates)})
    
    # 将因子合并到完整日期范围上，并填充
    df_factors = pd.merge(date_range_df, df_factors, on='date', how='left')
    df_factors['qfq_factor'] = df_factors['qfq_factor'].ffill().bfill().fillna(1.0)
    df_factors['hfq_factor'] = df_factors['hfq_factor'].ffill().bfill().fillna(1.0)
    df_factors['symbol'] = symbol
    
    log_event(
        logger=_LOG, service="integrator", level="INFO",
        event="integrate.success", message=f"Successfully integrated data for {symbol}",
        file=__file__, func="get_daily_bars_with_factors", line=0, trace_id=None
    )

    return {
        'bars': df_bars, 
        'factors': df_factors[['symbol', 'date', 'qfq_factor', 'hfq_factor']]
    }
