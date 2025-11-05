# backend/services/sync_data_fetcher.py
# ==============================
# 说明: 同步数据获取器 (Data Fetcher - V2.0 全链路追踪版)
# - 职责: 根据标的、频率、日期范围调用数据源并保存到数据库。
# - V2.0增强:
#   1. 接收并传递 trace_id
#   2. 详细的分阶段日志（调用integrator、保存bars、保存factors）
#   3. 精确的错误捕获和上报
# ==============================

from __future__ import annotations

import asyncio
from typing import Optional

from backend.services import integrators
from backend.db import upsert_candles_raw, upsert_factors
from backend.utils.common import infer_symbol_type
from backend.utils.logger import get_logger, log_event
from backend.utils.limiter import TaskContext

_LOG = get_logger("sync_data_fetcher")


async def fetch_and_save(
    symbol: str,
    freq: str,
    start_ymd: int,
    end_ymd: int,
    priority: int,
    trace_id: Optional[str] = None
):
    """
    根据标的、频率和日期范围，获取数据并保存到数据库（异步版本）。
    
    当前实现:
    - 日线（1d）：调用 integrators.get_daily_bars_with_factors
    - 其他频率：暂未实现，记录警告
    
    V2.0增强:
    - 全程使用 trace_id 标记日志
    - 详细记录每个子步骤（调用integrator、保存K线、保存因子）
    - 区分不同类型的失败（integrator失败、数据为空、保存失败）
    
    Args:
        symbol (str): 标的代码
        freq (str): 频率，如 '1d', '5m'
        start_ymd (int): 开始日期，YYYYMMDD
        end_ymd (int): 结束日期，YYYYMMDD
        priority (int): 任务优先级
        trace_id (str): 追踪ID，用于全链路日志关联
    """
    sec_type = infer_symbol_type(symbol)
    start_date_str = f"{start_ymd:08d}"
    end_date_str = f"{end_ymd:08d}"
    
    trace_prefix = f"[TRACE:{trace_id}]" if trace_id else ""

    with TaskContext(priority=priority):
        log_event(
            logger=_LOG, service="data_fetcher", level="INFO",
            event="fetch.start",
            message=f"{trace_prefix} Fetching {symbol}@{freq} from {start_date_str} to {end_date_str}",
            extra={
                "trace_id": trace_id,
                "symbol": symbol,
                "freq": freq,
                "sec_type": sec_type,
                "date_range": f"{start_date_str}-{end_date_str}"
            },
            file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
        )

        # 根据频率路由到不同的数据获取逻辑
        if freq == '1d':
            # --- 阶段1：调用集成器获取数据 ---
            log_event(
                logger=_LOG, service="data_fetcher", level="DEBUG",
                event="fetch.call_integrator",
                message=f"{trace_prefix} Calling integrator.get_daily_bars_with_factors",
                extra={"trace_id": trace_id, "symbol": symbol},
                file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
            )
            
            try:
                result = await integrators.get_daily_bars_with_factors(
                    symbol=symbol,
                    start_date=start_date_str,
                    end_date=end_date_str
                )
            except Exception as e:
                log_event(
                    logger=_LOG, service="data_fetcher", level="ERROR",
                    event="fetch.integrator_exception",
                    message=f"{trace_prefix} Integrator raised exception: {e}",
                    extra={
                        "trace_id": trace_id,
                        "error_message": str(e),
                        "error_type": type(e).__name__
                    },
                    file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                )
                raise  # 重新抛出，让上层 executor 捕获
            
            # --- 阶段2：验证返回结果 ---
            if not result:
                log_event(
                    logger=_LOG, service="data_fetcher", level="ERROR",
                    event="fetch.integrator_null",
                    message=f"{trace_prefix} Integrator returned None for {symbol}",
                    extra={"trace_id": trace_id, "symbol": symbol},
                    file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                )
                return  # 提前返回，不继续处理
            
            log_event(
                logger=_LOG, service="data_fetcher", level="DEBUG",
                event="fetch.integrator_success",
                message=f"{trace_prefix} Integrator returned data",
                extra={
                    "trace_id": trace_id,
                    "has_bars": 'bars' in result,
                    "has_factors": 'factors' in result
                },
                file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
            )
            
            df_bars = result.get('bars')
            df_factors = result.get('factors')
            
            # --- 阶段3：保存K线数据 ---
            if df_bars is not None and not df_bars.empty:
                log_event(
                    logger=_LOG, service="data_fetcher", level="DEBUG",
                    event="fetch.save_bars_start",
                    message=f"{trace_prefix} Saving {len(df_bars)} bars to candles_raw",
                    extra={
                        "trace_id": trace_id,
                        "symbol": symbol,
                        "freq": freq,
                        "rows": len(df_bars),
                        "date_range": f"{df_bars['ts'].min()}-{df_bars['ts'].max()}"
                    },
                    file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                )
                
                try:
                    df_bars['symbol'] = symbol
                    df_bars['freq'] = freq
                    df_bars['source'] = 'async_pipeline_v2'
                    
                    rows_affected = await asyncio.to_thread(upsert_candles_raw, df_bars.to_dict('records'))
                    
                    log_event(
                        logger=_LOG, service="data_fetcher", level="INFO",
                        event="fetch.saved_bars",
                        message=f"{trace_prefix} Successfully saved bars",
                        extra={
                            "trace_id": trace_id,
                            "symbol": symbol,
                            "freq": freq,
                            "rows_saved": len(df_bars),
                            "rows_affected": rows_affected
                        },
                        file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                    )
                except Exception as e:
                    log_event(
                        logger=_LOG, service="data_fetcher", level="ERROR",
                        event="fetch.save_bars_fail",
                        message=f"{trace_prefix} Failed to save bars to DB: {e}",
                        extra={
                            "trace_id": trace_id,
                            "error_message": str(e),
                            "error_type": type(e).__name__
                        },
                        file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                    )
                    raise
            else:
                log_event(
                    logger=_LOG, service="data_fetcher", level="WARN",
                    event="fetch.no_bars",
                    message=f"{trace_prefix} No bars data to save",
                    extra={"trace_id": trace_id, "symbol": symbol, "freq": freq},
                    file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                )
            
            # --- 阶段4：保存复权因子 ---
            if df_factors is not None and not df_factors.empty:
                log_event(
                    logger=_LOG, service="data_fetcher", level="DEBUG",
                    event="fetch.save_factors_start",
                    message=f"{trace_prefix} Saving {len(df_factors)} factor records to adj_factors",
                    extra={
                        "trace_id": trace_id,
                        "symbol": symbol,
                        "rows": len(df_factors)
                    },
                    file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                )
                
                try:
                    rows_affected = await asyncio.to_thread(upsert_factors, df_factors.to_dict('records'))
                    
                    log_event(
                        logger=_LOG, service="data_fetcher", level="INFO",
                        event="fetch.saved_factors",
                        message=f"{trace_prefix} Successfully saved factors",
                        extra={
                            "trace_id": trace_id,
                            "symbol": symbol,
                            "rows_saved": len(df_factors),
                            "rows_affected": rows_affected
                        },
                        file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                    )
                except Exception as e:
                    log_event(
                        logger=_LOG, service="data_fetcher", level="ERROR",
                        event="fetch.save_factors_fail",
                        message=f"{trace_prefix} Failed to save factors to DB: {e}",
                        extra={
                            "trace_id": trace_id,
                            "error_message": str(e),
                            "error_type": type(e).__name__
                        },
                        file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                    )
                    # 因子保存失败不应阻止整个任务（K线数据可能已保存）
                    # 记录错误但不抛出异常
            else:
                log_event(
                    logger=_LOG, service="data_fetcher", level="WARN",
                    event="fetch.no_factors",
                    message=f"{trace_prefix} No factor data to save",
                    extra={"trace_id": trace_id, "symbol": symbol},
                    file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
                )
        
        else:
            # 其他频率：暂未迁移到新数据体系
            log_event(
                logger=_LOG, service="data_fetcher", level="WARN",
                event="freq.not_supported",
                message=f"{trace_prefix} Frequency {freq} not yet migrated for {symbol}",
                extra={"trace_id": trace_id, "symbol": symbol, "freq": freq},
                file=__file__, func="fetch_and_save", line=0, trace_id=trace_id
            )
