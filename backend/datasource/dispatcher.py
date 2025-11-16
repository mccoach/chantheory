# backend/datasource/dispatcher.py
# ==============================
# V4.0 - 修复日/周/月路由
# ==============================

from __future__ import annotations
from typing import Tuple, Optional, Any
import pandas as pd
import inspect

from backend.utils.logger import get_logger, log_event
from backend.datasource.registry import get_methods_for_category
from backend.utils.error_classifier import classify_fetch_error, ErrorType

_LOG = get_logger("dispatcher")

async def fetch(
    data_category: str, 
    freq: Optional[str] = None,
    **kwargs: Any
) -> Tuple[Optional[pd.DataFrame | Any], Optional[str]]:
    """
    根据数据类别和参数，调度并获取原始数据（异步版本）
    
    V4.0 改动：
      - 修复日/周/月路由逻辑
      - 删除 period 参数的自动添加（由各自的适配器函数处理）
    """
    
    # ===== 核心修复：日/周/月独立路由 =====
    routed_category = data_category
    
    if data_category == 'stock_bars' and freq:
        freq_str = str(freq).strip().lower()
        
        # 分钟线 → stock_minutely_bars
        if freq_str in ['1m', '5m', '15m', '30m', '60m']:
            routed_category = 'stock_minutely_bars'
            _LOG.debug(f"[路由] stock_bars + {freq} → stock_minutely_bars")
        
        # 日K → stock_daily_bars
        elif freq_str == '1d':
            routed_category = 'stock_daily_bars'
            kwargs['period'] = 'daily'  # ← 传递给 get_stock_daily_em
            _LOG.debug(f"[路由] stock_bars + 1d → stock_daily_bars")
        
        # 周K → stock_weekly_bars
        elif freq_str == '1w':
            routed_category = 'stock_weekly_bars'
            # ❌ 删除：不再传递 period（由 get_stock_weekly_em 内部固定）
            _LOG.debug(f"[路由] stock_bars + 1w → stock_weekly_bars")
        
        # 月K → stock_monthly_bars
        elif freq_str == '1M':
            routed_category = 'stock_monthly_bars'
            # ❌ 删除：不再传递 period（由 get_stock_monthly_em 内部固定）
            _LOG.debug(f"[路由] stock_bars + 1M → stock_monthly_bars")
    
    # ===== 记录路由结果 =====
    if routed_category != data_category or kwargs.get('period'):
        _LOG.info(
            f"[路由决策] {kwargs.get('symbol', 'N/A')} {freq}: "
            f"类型={kwargs.get('symbol_type', 'N/A')} → "
            f"category={routed_category} "
            f"period={kwargs.get('period', 'N/A')}"
        )
    
    # ===== 使用路由后的 category =====
    methods = get_methods_for_category(routed_category)
    if not methods:
        log_event(
            logger=_LOG, service="dispatcher", level="ERROR",
            event="fetch.no_methods", 
            message=f"No methods for category: {routed_category}",
            extra={
                "category": routed_category, 
                "original_category": data_category, 
                "freq": freq
            }, 
            file=__file__, func="fetch", line=0, trace_id=None
        )
        return None, None

    last_error = None
    last_error_type = None
    
    for method in methods:
        log_event(
            logger=_LOG, service="dispatcher", level="DEBUG",
            event="fetch.try", message=f"Trying {method.id}",
            extra={
                "method_id": method.id, 
                "priority": method.priority, 
                "params": kwargs
            },
            file=__file__, func="fetch", line=0, trace_id=None
        )
        
        raw_data = None
        exception_caught = None
        
        try:
            # ===== V3.0 新增：智能参数过滤 =====
            sig = inspect.signature(method.callable)
            accepted_params = set(sig.parameters.keys())
            
            # 只传入函数签名中存在的参数
            filtered_kwargs = {
                k: v for k, v in kwargs.items() 
                if k in accepted_params
            }
            
            # 记录参数过滤（调试用）
            if len(filtered_kwargs) < len(kwargs):
                removed = set(kwargs.keys()) - set(filtered_kwargs.keys())
                _LOG.debug(
                    f"[参数过滤] {method.id}: "
                    f"移除 {removed} (函数不接受这些参数)"
                )
            
            # ===== 核心调用（使用过滤后的参数）=====
            raw_data = await method.callable(**filtered_kwargs)
            
        except Exception as e:
            exception_caught = e
        
        # 使用异常分类器进行精确分类
        error_type, error_message, suggestion = classify_fetch_error(exception_caught, raw_data)
        
        # 情况1：成功
        if error_type == "success":
            log_event(
                logger=_LOG, service="dispatcher", level="INFO",
                event="fetch.success", 
                message=f"Method {method.id} succeeded",
                extra={
                    "method_id": method.id, 
                    "data_rows": len(raw_data) if isinstance(raw_data, pd.DataFrame) else "N/A"
                },
                file=__file__, func="fetch", line=0, trace_id=None
            )
            return raw_data, method.id
        
        # 情况2：返回空数据（非异常）
        if error_type == ErrorType.EMPTY_RESPONSE:
            log_event(
                logger=_LOG, service="dispatcher", level="WARN",
                event="fetch.empty", 
                message=f"Method {method.id} returned empty data",
                extra={
                    "method_id": method.id,
                    "error_type": error_type,
                    "error_message": error_message,
                    "suggestion": suggestion,
                    "params": kwargs
                },
                file=__file__, func="fetch", line=0, trace_id=None
            )
            last_error = ValueError(error_message)
            last_error_type = error_type
            continue
        
        # 情况3：反爬虫封禁（最严重）
        if error_type == ErrorType.ANTISPIDER:
            log_event(
                logger=_LOG, service="dispatcher", level="CRITICAL",
                event="fetch.antispider", 
                message=f"ANTISPIDER DETECTED: {method.id}",
                extra={
                    "method_id": method.id,
                    "error_type": error_type,
                    "error_message": error_message,
                    "suggestion": suggestion,
                    "params": kwargs,
                    "exception_details": str(exception_caught)
                },
                file=__file__, func="fetch", line=0, trace_id=None
            )
            
            # 发布系统级告警事件
            from backend.utils.events import publish as publish_event
            publish_event({
                "type": "system_alert",
                "level": "critical",
                "code": "ANTISPIDER_TRIGGERED",
                "message": f"数据源 {method.provider} 的方法 {method.id} 疑似触发反爬虫机制",
                "details": error_message,
                "suggestion": suggestion,
            })
            
            last_error = exception_caught
            last_error_type = error_type
            continue
        
        # 情况4：其他错误
        log_level = "ERROR" if error_type == ErrorType.API_CHANGED else "WARN"
        log_event(
            logger=_LOG, service="dispatcher", level=log_level,
            event=f"fetch.{error_type}", 
            message=f"Method {method.id} failed",
            extra={
                "method_id": method.id,
                "error_type": error_type,
                "error_message": error_message,
                "suggestion": suggestion,
                "params": kwargs,
                "exception_details": str(exception_caught)
            },
            file=__file__, func="fetch", line=0, trace_id=None
        )
        
        last_error = exception_caught
        last_error_type = error_type
        continue

    # 全部方法都失败
    log_event(
        logger=_LOG, service="dispatcher", level="CRITICAL",
        event="fetch.all_fail", 
        message=f"All methods failed for category: {routed_category}",
        extra={
            "category": routed_category,
            "original_category": data_category,
            "freq": freq,
            "last_error_type": last_error_type,
            "last_error": str(last_error),
            "params": kwargs,
            "attempted_methods": [m.id for m in methods]
        },
        file=__file__, func="fetch", line=0, trace_id=None
    )
    
    return None, None