# backend/datasource/dispatcher.py
# ==============================
# 说明: 数据源统一调度器 (The Executor - 全异步版)
# - 职责: 根据数据类别，按优先级依次尝试异步方法，直到成功或全部失败。
# - 设计: 
#   * 异步执行：与新的全异步数据链路保持一致。
#   * 单次尝试：不内置重试（重试由上层使用 async_retry_call 控制）。
#   * 极简逻辑：核心只有一个 for 循环。
# ==============================

from __future__ import annotations
from typing import Tuple, Optional, Any
import pandas as pd

from backend.utils.logger import get_logger, log_event
from backend.datasource.registry import get_methods_for_category
from backend.utils.error_classifier import classify_fetch_error, ErrorType

_LOG = get_logger("datasource.dispatcher")

async def fetch(
    data_category: str, 
    **kwargs: Any
) -> Tuple[Optional[pd.DataFrame | Any], Optional[str]]:
    """
    根据数据类别和参数，调度并获取原始数据（异步版本）。

    Args:
        data_category (str): 标准化的数据类别，如 'stock_bars', 'adj_factor'。
        **kwargs: 传递给原子化调用函数的参数，如 symbol, start_date。

    Returns:
        Tuple[Optional[pd.DataFrame | Any], Optional[str]]: 
            成功时返回 (原始数据, 使用的方法ID)
            失败时返回 (None, None)
    """
    methods = get_methods_for_category(data_category)
    if not methods:
        log_event(
            logger=_LOG, service="dispatcher", level="ERROR",
            event="fetch.no_methods", message=f"No methods for category: {data_category}",
            extra={"category": data_category}, file=__file__, func="fetch", line=0, trace_id=None
        )
        return None, None

    last_error = None
    last_error_type = None
    
    for method in methods:
        log_event(
            logger=_LOG, service="dispatcher", level="DEBUG",
            event="fetch.try", message=f"Trying {method.id}",
            extra={"method_id": method.id, "priority": method.priority, "params": kwargs},
            file=__file__, func="fetch", line=0, trace_id=None
        )
        
        raw_data = None
        exception_caught = None
        
        try:
            # 核心：直接 await 异步的 callable
            raw_data = await method.callable(**kwargs)
            
        except Exception as e:
            exception_caught = e
        
        # 使用异常分类器进行精确分类
        error_type, error_message, suggestion = classify_fetch_error(exception_caught, raw_data)
        
        # 情况1：成功
        if error_type == "success":
            log_event(
                logger=_LOG, service="dispatcher", level="INFO",
                event="fetch.success", message=f"Method {method.id} succeeded",
                extra={"method_id": method.id, "data_rows": len(raw_data) if isinstance(raw_data, pd.DataFrame) else "N/A"},
                file=__file__, func="fetch", line=0, trace_id=None
            )
            return raw_data, method.id
        
        # 情况2：返回空数据（非异常）
        if error_type == ErrorType.EMPTY_RESPONSE:
            log_event(
                logger=_LOG, service="dispatcher", level="WARN",
                event="fetch.empty", message=f"Method {method.id} returned empty data",
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
                event="fetch.antispider", message=f"ANTISPIDER DETECTED: {method.id}",
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
            event=f"fetch.{error_type}", message=f"Method {method.id} failed",
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
        event="fetch.all_fail", message=f"All methods failed for category: {data_category}",
        extra={
            "category": data_category,
            "last_error_type": last_error_type,
            "last_error": str(last_error),
            "params": kwargs,
            "attempted_methods": [m.id for m in methods]
        },
        file=__file__, func="fetch", line=0, trace_id=None
    )
    
    return None, None
