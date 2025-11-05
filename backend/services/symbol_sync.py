# backend/services/symbol_sync.py
# ==============================
# 说明：标的列表同步服务（V3.1 完整版 - 支持A股/ETF/LOF）
# 改动：
#   1. 分别拉取A股、ETF、LOF三类
#   2. 各自标准化后合并
#   3. 统一落库
# ==============================

from __future__ import annotations

import asyncio
from datetime import datetime
import pandas as pd

from backend.datasource import dispatcher
from backend.services.normalizer import normalize_symbol_list_df
from backend.db.symbols import upsert_symbol_index
from backend.utils.logger import get_logger, log_event
from backend.settings import settings

_LOG = get_logger("symbol_sync")

async def sync_all_symbols() -> bool:
    """
    同步全市场标的列表（A股 + ETF + LOF）
    
    策略：
      1. 根据 settings.sync_symbol_categories 决定拉取哪些类别
      2. 分别调用对应的 dispatcher category
      3. 各自标准化后合并
      4. 统一落库
    
    Returns:
        bool: 同步是否成功
    """
    
    log_event(
        logger=_LOG,
        service="symbol_sync",
        level="INFO",
        file=__file__,
        func="sync_all_symbols",
        line=0,
        trace_id=None,
        event="sync.start",
        message="开始同步标的列表",
        extra={"categories": settings.sync_symbol_categories}
    )
    
    try:
        all_dataframes = []
        
        # 1. A股列表
        if 'A' in settings.sync_symbol_categories:
            _LOG.info("[标的同步] 拉取A股列表")
            
            a_raw, a_src = await dispatcher.fetch('stock_list')
            
            if a_raw is not None and not a_raw.empty:
                a_clean = normalize_symbol_list_df(a_raw, category='A')
                if a_clean is not None and not a_clean.empty:
                    all_dataframes.append(a_clean)
                    _LOG.info(f"[标的同步] A股：{len(a_clean)} 个")
            else:
                _LOG.warning("[标的同步] A股拉取失败或为空")
        
        # 2. ETF列表
        if 'ETF' in settings.sync_symbol_categories:
            _LOG.info("[标的同步] 拉取ETF列表")
            
            etf_raw, etf_src = await dispatcher.fetch('etf_list')
            
            if etf_raw is not None and not etf_raw.empty:
                etf_clean = normalize_symbol_list_df(etf_raw, category='ETF')
                if etf_clean is not None and not etf_clean.empty:
                    all_dataframes.append(etf_clean)
                    _LOG.info(f"[标的同步] ETF：{len(etf_clean)} 个")
            else:
                _LOG.warning("[标的同步] ETF拉取失败或为空")
        
        # 3. LOF列表
        if 'LOF' in settings.sync_symbol_categories:
            _LOG.info("[标的同步] 拉取LOF列表")
            
            lof_raw, lof_src = await dispatcher.fetch('lof_list')
            
            if lof_raw is not None and not lof_raw.empty:
                lof_clean = normalize_symbol_list_df(lof_raw, category='LOF')
                if lof_clean is not None and not lof_clean.empty:
                    all_dataframes.append(lof_clean)
                    _LOG.info(f"[标的同步] LOF：{len(lof_clean)} 个")
            else:
                _LOG.warning("[标的同步] LOF拉取失败或为空")
        
        # 4. 合并所有类别
        if not all_dataframes:
            _LOG.error("[标的同步] 所有类别拉取失败")
            return False
        
        merged = pd.concat(all_dataframes, ignore_index=True)
        
        # 5. 补充updated_at
        merged['updated_at'] = datetime.now().isoformat()
        
        # 6. 统一落库
        await asyncio.to_thread(
            upsert_symbol_index,
            merged.to_dict('records')
        )
        
        log_event(
            logger=_LOG,
            service="symbol_sync",
            level="INFO",
            file=__file__,
            func="sync_all_symbols",
            line=0,
            trace_id=None,
            event="sync.done",
            message=f"标的列表同步完成，共 {len(merged)} 个标的",
            extra={
                "total": len(merged),
                "by_category": {
                    'A': len(all_dataframes[0]) if len(all_dataframes) > 0 else 0,
                    'ETF': len(all_dataframes[1]) if len(all_dataframes) > 1 else 0,
                    'LOF': len(all_dataframes[2]) if len(all_dataframes) > 2 else 0,
                }
            }
        )
        
        return True
    
    except Exception as e:
        log_event(
            logger=_LOG,
            service="symbol_sync",
            level="ERROR",
            file=__file__,
            func="sync_all_symbols",
            line=0,
            trace_id=None,
            event="sync.error",
            message=f"标的列表同步失败: {e}",
            extra={"error": str(e)}
        )
        return False

# ========== NEW: 阻塞版交易日历同步 ==========

async def sync_trade_calendar_blocking() -> bool:
    """
    同步交易日历（阻塞版，用于启动时优先执行）
    
    与普通任务的区别：
      - 直接调用，不走任务队列
      - 阻塞等待完成
      - 确保交易日历表可用
    
    Returns:
        bool: 同步是否成功
    """
    log_event(
        logger=_LOG,
        service="symbol_sync",
        level="INFO",
        file=__file__,
        func="sync_trade_calendar_blocking",
        line=0,
        trace_id=None,
        event="calendar.sync.start",
        message="开始同步交易日历（阻塞）"
    )
    
    try:
        from backend.services.normalizer import normalize_trade_calendar_df
        from backend.db.calendar import upsert_trade_calendar
        
        # 拉取
        raw_df, source_id = await dispatcher.fetch('trade_calendar')
        
        if raw_df is None or raw_df.empty:
            _LOG.error("[日历同步] 拉取失败，返回为空")
            return False
        
        # 标准化
        clean_df = normalize_trade_calendar_df(raw_df)
        
        if clean_df is None or clean_df.empty:
            _LOG.error("[日历同步] 标准化后为空失败")
            return False
        
        # 转为记录格式
        records = [
            {
                'date': int(row['date']),
                'market': 'CN',
                'is_trading_day': 1
            }
            for _, row in clean_df.iterrows()
        ]
        
        # 落库
        await asyncio.to_thread(upsert_trade_calendar, records)
        
        log_event(
            logger=_LOG,
            service="symbol_sync",
            level="INFO",
            file=__file__,
            func="sync_trade_calendar_blocking",
            line=0,
            trace_id=None,
            event="calendar.sync.done",
            message=f"交易日历同步完成，共 {len(records)} 个交易日",
            extra={"count": len(records)}
        )
        
        return True
    
    except Exception as e:
        log_event(
            logger=_LOG,
            service="symbol_sync",
            level="ERROR",
            file=__file__,
            func="sync_trade_calendar_blocking",
            line=0,
            trace_id=None,
            event="calendar.sync.error",
            message=f"交易日历同步失败: {e}",
            extra={"error": str(e)}
        )
        return False
