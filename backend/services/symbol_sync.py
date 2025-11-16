# backend/services/symbol_sync.py
# ==============================
# 说明：标的列表同步服务（V7.0 - 移除sync_symbol_categories）
# 
# 职责边界说明：
#   - 编排拉取流程
#   - 推送实时进度SSE（⚠️ 特例：本模块需要进度反馈）
#   - 返回详细执行结果
# 
# V7.0 改动：
#   - 删除所有 settings.sync_symbol_categories 引用
#   - 改为固定同步 A/ETF/LOF（无条件执行）
# ==============================

from __future__ import annotations

import asyncio
from datetime import datetime

from backend.services.sync_helper import (
    fetch_normalize_save,
    build_exchange_event,
    build_fallback_event
)

from backend.datasource import dispatcher
from backend.services.normalizer import normalize_symbol_list_df
from backend.db.connection import get_conn
from backend.utils.events import publish as publish_event
from backend.utils.logger import get_logger, log_event
from backend.settings import settings

_LOG = get_logger("symbol_sync")


async def sync_all_symbols() -> dict:
    """
    同步全市场标的列表（固定同步 A/ETF/LOF）
    
    Returns:
        {
            'success': bool,
            'strategy': 'official' | 'fallback' | 'failed',
            'exchanges': {
                'sh': {'status': 'success', 'count': 2292},
                'sz': {'status': 'success', 'count': 2875},
                'bj': {'status': 'failed', 'error': '...'}
            },
            'fallback': {'status': 'success', 'count': 5400} | None,
            'total_in_db': 5400
        }
    """
    
    log_event(
        logger=_LOG, service="symbol_sync", level="INFO",
        file=__file__, func="sync_all_symbols", line=0, trace_id=None,
        event="sync.start", message="开始同步标的列表（固定同步A/ETF/LOF）",
        extra={"categories": ["A", "ETF", "LOF"]}
    )
    
    summary = {
        'success': False,
        'strategy': None,
        'exchanges': {},
        'fallback': None,
        'total_in_db': 0
    }
    
    try:
        # ===== A股同步（无条件执行）=====
        _LOG.info("[标的同步] 并发拉取三交所")
        
        # 定义任务
        tasks = [
            ('stock_list_sh', 'sh', '上交所'),
            ('stock_list_sz', 'sz', '深交所'),
            ('stock_list_bj', 'bj', '北交所')
        ]
        
        # 并发执行（成功就落库+推送SSE）
        results = await asyncio.gather(*[
            _sync_with_sse(cat, code, name) for cat, code, name in tasks
        ])
        
        sh_result, sz_result, bj_result = results
        summary['exchanges'] = {'sh': sh_result, 'sz': sz_result, 'bj': bj_result}
        
        success_count = sum(1 for r in results if r['status'] == 'success')
        _LOG.info(f"[标的同步] 三交所结果：{success_count}/3 成功")
        
        # 判定策略
        if success_count == 3:
            summary['strategy'] = 'official'
            _LOG.info("[标的同步] 三交所全部成功 ✅")
        elif success_count == 2 and bj_result['status'] == 'failed':
            summary['strategy'] = 'official'
            _LOG.warning("[标的同步] 仅北交所失败 ⚠️")
        else:
            # 降级
            _LOG.warning(f"[标的同步] 降级备用方案")
            fallback = await _sync_fallback_with_sse()
            summary['fallback'] = fallback
            summary['strategy'] = 'fallback' if fallback['status'] == 'success' else 'failed'
        
        # ===== ETF/LOF同步（无条件执行）=====
        await _sync_etf_lof()
        
        # ===== 统计总数 =====
        summary['total_in_db'] = await asyncio.to_thread(_count_symbols_in_db)
        summary['success'] = summary['strategy'] in ['official', 'fallback']
        
        log_event(
            logger=_LOG, service="symbol_sync", level="INFO",
            file=__file__, func="sync_all_symbols", line=0, trace_id=None,
            event="sync.done", message="标的列表同步完成", extra=summary
        )
        
        return summary
    
    except Exception as e:
        log_event(
            logger=_LOG, service="symbol_sync", level="ERROR",
            file=__file__, func="sync_all_symbols", line=0, trace_id=None,
            event="sync.error", message=f"失败: {e}", extra={"error": str(e)}
        )
        
        return {
            'success': False, 'strategy': 'failed',
            'exchanges': {}, 'fallback': None, 'total_in_db': 0
        }


async def _sync_with_sse(category: str, exchange_code: str, display_name: str) -> dict:
    """同步单个交易所（复用通用流程+推送SSE）"""
    result = await fetch_normalize_save(
        category=category,
        normalizer=normalize_symbol_list_df,
        display_name=display_name,
        symbol_type='A'
    )
    publish_event(build_exchange_event(exchange_code, display_name, result))
    return result


async def _sync_fallback_with_sse() -> dict:
    """备用方案（复用通用流程+推送SSE）"""
    result = await fetch_normalize_save(
        category='stock_list',
        normalizer=normalize_symbol_list_df,
        display_name='东财（备用）',
        symbol_type='A'
    )
    publish_event(build_fallback_event(result))
    return result


async def _sync_etf_lof():
    """同步ETF/LOF（无条件执行）"""
    _LOG.info("[标的同步] 拉取ETF")
    await fetch_normalize_save(
        category='etf_list',
        normalizer=normalize_symbol_list_df,
        display_name='ETF',
        symbol_type='ETF'  
    )
    
    _LOG.info("[标的同步] 拉取LOF")
    await fetch_normalize_save(
        category='lof_list',
        normalizer=normalize_symbol_list_df,
        display_name='LOF',
        symbol_type='LOF'  
    )


def _count_symbols_in_db() -> int:
    """统计数据库标的总数"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM symbol_index;")
    result = cur.fetchone()
    return result[0] if result else 0


# ========== 交易日历同步 ==========

async def sync_trade_calendar_blocking() -> bool:
    """同步交易日历（阻塞版）"""
    
    log_event(
        logger=_LOG, service="symbol_sync", level="INFO",
        file=__file__, func="sync_trade_calendar_blocking", line=0, trace_id=None,
        event="calendar.sync.start", message="开始同步交易日历"
    )
    
    try:
        from backend.services.normalizer import normalize_trade_calendar_df
        from backend.db.calendar import upsert_trade_calendar
        
        raw_df, _ = await dispatcher.fetch('trade_calendar')
        if raw_df is None or raw_df.empty:
            _LOG.error("[日历同步] 拉取失败")
            return False
        
        clean_df = normalize_trade_calendar_df(raw_df)
        if clean_df is None or clean_df.empty:
            _LOG.error("[日历同步] 标准化失败")
            return False
        
        records = [
            {'date': int(row['date']), 'market': 'CN', 'is_trading_day': 1}
            for _, row in clean_df.iterrows()
        ]
        
        await asyncio.to_thread(upsert_trade_calendar, records)
        
        log_event(
            logger=_LOG, service="symbol_sync", level="INFO",
            file=__file__, func="sync_trade_calendar_blocking", line=0, trace_id=None,
            event="calendar.sync.done", message=f"交易日历同步完成，共 {len(records)} 个",
            extra={"count": len(records)}
        )
        
        return True
    
    except Exception as e:
        log_event(
            logger=_LOG, service="symbol_sync", level="ERROR",
            file=__file__, func="sync_trade_calendar_blocking", line=0, trace_id=None,
            event="calendar.sync.error", message=f"失败: {e}", extra={"error": str(e)}
        )
        return False