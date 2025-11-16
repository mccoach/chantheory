# backend/services/sync_helper.py
# ==============================
# 说明：同步任务通用辅助函数（V2.0 - 强化日志版）
# 职责：
#   - 提供可复用的"拉取-标准化-落库"流程
#   - 每步详细日志（用于诊断）
#   - 提供SSE事件构造函数
# 改动：
#   - 每个步骤都打印详细日志
#   - 捕获并记录SQLite错误
#   - exc_info=True 记录完整堆栈
# ==============================

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable

from backend.datasource import dispatcher
from backend.db.symbols import upsert_symbol_index
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("sync_helper")


async def fetch_normalize_save(
    category: str,
    normalizer: Callable,
    display_name: str,
    symbol_type: str
) -> dict:
    """
    通用的"拉取-标准化-落库"流程（详细日志版）
    
    Args:
        category: dispatcher category（如 'stock_list_sh'）
        normalizer: 标准化函数（如 normalize_symbol_list_df）
        display_name: 显示名称（用于日志）
        symbol_type: 标的类型（传给normalizer的category参数，如 'A', 'ETF'）
    
    Returns:
        {
            'status': 'success' | 'failed',
            'count': int,
            'error': str (失败时)
        }
    """
    try:
        # ===== 步骤1：拉取 =====
        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.fetch.start",
            message=f"[同步] {display_name} 开始拉取...",
            extra={"category": category, "display_name": display_name}
        )
        
        raw_df, source_id = await dispatcher.fetch(category)
        
        if raw_df is None or raw_df.empty:
            error_msg = f"{display_name}拉取为空"
            
            log_event(
                logger=_LOG, service="sync_helper", level="ERROR",
                file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
                event="sync.fetch.empty",
                message=f"[同步] {error_msg}",
                extra={"category": category, "source_id": source_id}
            )
            
            return {'status': 'failed', 'count': 0, 'error': error_msg}
        
        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.fetch.success",
            message=f"[同步] {display_name} 拉取成功：{len(raw_df)} 行",
            extra={
                "category": category,
                "source_id": source_id,
                "rows": len(raw_df),
                "columns": raw_df.columns.tolist()
            }
        )
        
        # ===== 步骤2：标准化 =====
        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.normalize.start",
            message=f"[同步] {display_name} 开始标准化...",
            extra={"category": category}
        )
        
        clean_df = normalizer(raw_df, category=symbol_type)
        
        if clean_df is None or clean_df.empty:
            error_msg = f"{display_name}标准化失败"
            
            log_event(
                logger=_LOG, service="sync_helper", level="ERROR",
                file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
                event="sync.normalize.empty",
                message=f"[同步] {error_msg}",
                extra={"category": category}
            )
            
            return {'status': 'failed', 'count': 0, 'error': error_msg}
        
        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.normalize.success",
            message=f"[同步] {display_name} 标准化成功：{len(clean_df)} 行",
            extra={
                "category": category,
                "rows": len(clean_df),
                "sample": clean_df.head(3).to_dict('records')
            }
        )
        
        # ===== 步骤3：准备落库数据 =====
        clean_df['updated_at'] = datetime.now().isoformat()
        records = clean_df.to_dict('records')
        
        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.save.start",
            message=f"[同步] {display_name} 开始落库：{len(records)} 条",
            extra={"category": category, "rows": len(records)}
        )
        
        # ===== 步骤4：落库（详细错误捕获）=====
        try:
            row_count = await asyncio.to_thread(upsert_symbol_index, records)
            
            log_event(
                logger=_LOG, service="sync_helper", level="INFO",
                file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
                event="sync.save.success",
                message=f"[同步] {display_name} 落库成功：影响 {row_count} 行",
                extra={
                    "category": category,
                    "rows_inserted": len(records),
                    "rows_affected": row_count
                }
            )
        
        except Exception as db_error:
            error_msg = f"{display_name}落库失败: {type(db_error).__name__}: {str(db_error)}"
            
            log_event(
                logger=_LOG, service="sync_helper", level="ERROR",
                file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
                event="sync.save.fail",
                message=f"[同步] {error_msg}",
                extra={
                    "category": category,
                    "error_type": type(db_error).__name__,
                    "error_message": str(db_error),
                    "traceback": True  # ← 触发完整堆栈输出
                },
                exc_info=True  # ← 关键：打印完整异常堆栈
            )
            
            return {
                'status': 'failed',
                'count': 0,
                'error': error_msg
            }
        
        # ===== 步骤5：成功返回 =====
        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.complete",
            message=f"[同步] {display_name}：{len(records)} 个 ✅",
            extra={"category": category, "count": len(records)}
        )
        
        return {'status': 'success', 'count': len(records)}
    
    except Exception as e:
        error_msg = f"{display_name}整体异常: {type(e).__name__}: {str(e)}"
        
        log_event(
            logger=_LOG, service="sync_helper", level="ERROR",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.exception",
            message=f"[同步] {error_msg}",
            extra={
                "category": category,
                "error_type": type(e).__name__,
                "error_message": str(e)
            },
            exc_info=True
        )
        
        return {
            'status': 'failed',
            'count': 0,
            'error': error_msg
        }


def build_exchange_event(exchange_code: str, exchange_name: str, result: dict) -> dict:
    """
    构造交易所同步完成事件
    
    Args:
        exchange_code: 交易所代码（'sh', 'sz', 'bj'）
        exchange_name: 显示名称（'上交所', '深交所', '北交所'）
        result: fetch_normalize_save 的返回结果
    
    Returns:
        SSE事件字典
    """
    event = {
        'type': 'exchange_sync_complete',
        'scope': 'global',
        'exchange': exchange_code,
        'exchange_name': exchange_name,
        'status': result['status'],
        'timestamp': datetime.now().isoformat()
    }
    
    if result['status'] == 'success':
        event['count'] = result['count']
    else:
        event['error'] = result.get('error', '未知错误')
    
    return event


def build_fallback_event(result: dict) -> dict:
    """
    构造备用方案完成事件
    
    Args:
        result: fetch_normalize_save 的返回结果
    
    Returns:
        SSE事件字典
    """
    event = {
        'type': 'fallback_sync_complete',
        'scope': 'global',
        'source': 'eastmoney',
        'status': result['status'],
        'timestamp': datetime.now().isoformat()
    }
    
    if result['status'] == 'success':
        event['count'] = result['count']
    else:
        event['error'] = result.get('error', '未知错误')
    
    return event