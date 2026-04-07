# backend/datasource/dispatcher.py
# ==============================
# 数据调度器（最终基础数据收口版）
#
# 当前正式用途：
#   - trade_calendar
#   - symbol_list_sh / symbol_list_sz / symbol_list_bj
#   - profile_snapshot
#   - gbbq_events_raw
#
# 说明：
#   - 普通行情远程实时主链已不再走 dispatcher
#   - 远程普通 HQ 直接由 services/bars_recipes.py 调用 tdx_remote_adapter
# ==============================

from __future__ import annotations
from typing import Tuple, Optional, Any
import pandas as pd
import inspect

from backend.utils.logger import get_logger, log_event
from backend.datasource.registry import get_methods_for_category
from backend.utils.error_classifier import classify_fetch_error, ErrorType
from backend.utils.alerts import emit_system_alert

_LOG = get_logger("dispatcher")


async def fetch(
    data_category: str,
    freq: Optional[str] = None,
    **kwargs: Any,
) -> Tuple[Optional[pd.DataFrame | Any], Optional[str]]:
    category = data_category

    if freq is not None and "freq" not in kwargs:
        kwargs["freq"] = freq

    methods = get_methods_for_category(category)
    if not methods:
        log_event(
            logger=_LOG,
            service="dispatcher",
            level="ERROR",
            event="fetch.no_methods",
            message=f"No methods for category: {category}",
            extra={
                "category": category,
                "original_category": data_category,
                "freq": freq,
            },
            file=__file__,
            func="fetch",
            line=0,
            trace_id=None,
        )
        return None, None

    last_error: Optional[Exception] = None
    last_error_type: Optional[str] = None

    for method in methods:
        log_event(
            logger=_LOG,
            service="dispatcher",
            level="DEBUG",
            event="fetch.try",
            message=f"Trying {method.id}",
            extra={
                "method_id": method.id,
                "priority": method.priority,
                "params": kwargs,
            },
            file=__file__,
            func="fetch",
            line=0,
            trace_id=None,
        )

        raw_data = None
        exception_caught: Optional[Exception] = None

        try:
            sig = inspect.signature(method.callable)
            accepted_params = set(sig.parameters.keys())
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in accepted_params}
            raw_data = await method.callable(**filtered_kwargs)
        except Exception as e:
            exception_caught = e

        error_type, error_message, suggestion = classify_fetch_error(
            exception_caught, raw_data
        )

        if error_type == "success":
            log_event(
                logger=_LOG,
                service="dispatcher",
                level="INFO",
                event="fetch.success",
                message=f"Method {method.id} succeeded",
                extra={
                    "method_id": method.id,
                    "data_rows": len(raw_data) if isinstance(raw_data, pd.DataFrame) else "N/A",
                },
                file=__file__,
                func="fetch",
                line=0,
                trace_id=None,
            )
            return raw_data, method.id

        if error_type == ErrorType.EMPTY_RESPONSE:
            log_event(
                logger=_LOG,
                service="dispatcher",
                level="WARN",
                event="fetch.empty",
                message=f"Method {method.id} returned empty data",
                extra={
                    "method_id": method.id,
                    "error_type": error_type,
                    "error_message": error_message,
                    "suggestion": suggestion,
                    "params": kwargs,
                },
                file=__file__,
                func="fetch",
                line=0,
                trace_id=None,
            )
            last_error = ValueError(error_message)
            last_error_type = error_type
            continue

        if error_type == ErrorType.ANTISPIDER:
            log_event(
                logger=_LOG,
                service="dispatcher",
                level="CRITICAL",
                event="fetch.antispider",
                message=f"ANTISPIDER DETECTED: {method.id}",
                extra={
                    "method_id": method.id,
                    "error_type": error_type,
                    "error_message": error_message,
                    "suggestion": suggestion,
                    "params": kwargs,
                    "exception_details": str(exception_caught),
                },
                file=__file__,
                func="fetch",
                line=0,
                trace_id=None,
            )

            emit_system_alert(
                level="critical",
                code="ANTISPIDER_TRIGGERED",
                message=f"数据源 {method.provider} 的方法 {method.id} 疑似触发反爬虫机制",
                details=error_message,
                source=f"dispatcher.{method.provider}",
                trace_id=None,
                extra={
                    "method_id": method.id,
                    "provider": method.provider,
                    "category": category,
                },
            )

            last_error = exception_caught
            last_error_type = error_type
            continue

        log_level = "ERROR" if error_type == ErrorType.API_CHANGED else "WARN"
        log_event(
            logger=_LOG,
            service="dispatcher",
            level=log_level,
            event=f"fetch.{error_type}",
            message=f"Method {method.id} failed",
            extra={
                "method_id": method.id,
                "error_type": error_type,
                "error_message": error_message,
                "suggestion": suggestion,
                "params": kwargs,
                "exception_details": str(exception_caught),
            },
            file=__file__,
            func="fetch",
            line=0,
            trace_id=None,
        )

        last_error = exception_caught
        last_error_type = error_type
        continue

    log_event(
        logger=_LOG,
        service="dispatcher",
        level="CRITICAL",
        event="fetch.all_fail",
        message=f"All methods failed for category: {category}",
        extra={
            "category": category,
            "original_category": data_category,
            "freq": freq,
            "last_error_type": last_error_type,
            "last_error": str(last_error),
            "params": kwargs,
            "attempted_methods": [m.id for m in methods],
        },
        file=__file__,
        func="fetch",
        line=0,
        trace_id=None,
    )

    return None, None
