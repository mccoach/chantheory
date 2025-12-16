# backend/datasource/dispatcher.py
# ==============================
# V5.0 - 统一 freq 通道 + 去除 period/stock_bars 路由
#
# 设计要点：
#   1. data_category 只负责选择「方法集合」（由 registry 决定）；
#   2. freq 是系统内统一的频率参数：
#        - '1m','5m','15m','30m','60m','1d','1w','1M'
#        - dispatcher 负责把 freq 透传给需要它的 provider（如 EastMoney / Sina）；
#        - 对不接受 freq 的方法，签名过滤会自动丢弃该参数；
#   3. 不再支持历史上的 'stock_bars' → 'stock_daily_bars' 等二级路由；
#      调用方必须显式使用 registry 中声明的 category：
#        - 'stock_daily_bars' / 'stock_weekly_bars' / 'stock_monthly_bars'
#        - 'stock_minutely_bars' / 'fund_bars' / 'fund_minutely_bars'
#        - 'stock_list_sh' / 'stock_list_sz' / 'fund_list_sh' / 'fund_list_sz'
#        - 'trade_calendar' / 'adj_factor' 等
#   4. 其他能力保持不变：
#        - 多方法按优先级依次尝试；
#        - 参数白名单过滤（基于函数签名）；
#        - 精细错误分类（含反爬告警）；
#        - 结构化日志。
#
# 改动（Schema统一）：
#   - ANTISPIDER 分支发出的 system_alert 事件使用统一 Schema：
#       {
#         "type": "system_alert",
#         "level": "critical",
#         "code": "ANTISPIDER_TRIGGERED",
#         "message": "...",
#         "details": "...",
#         "source": "dispatcher.<provider>",
#         "trace_id": null,
#         "timestamp": "ISO8601"
#       }
# ==============================

from __future__ import annotations
from typing import Tuple, Optional, Any
import pandas as pd
import inspect

from backend.utils.logger import get_logger, log_event
from backend.datasource.registry import get_methods_for_category
from backend.utils.error_classifier import classify_fetch_error, ErrorType
from backend.utils.time import now_iso

_LOG = get_logger("dispatcher")


async def fetch(
    data_category: str,
    freq: Optional[str] = None,
    **kwargs: Any,
) -> Tuple[Optional[pd.DataFrame | Any], Optional[str]]:
    """
    根据数据类别和参数，调度并获取原始数据（异步版本）

    参数语义：
      - data_category:
          与 registry.METHOD_CATALOG 的 key 一一对应：
            * 'stock_daily_bars' / 'stock_weekly_bars' / 'stock_monthly_bars'
            * 'stock_minutely_bars' / 'fund_bars' / 'fund_minutely_bars'
            * 'stock_list_sh' / 'stock_list_sz' / 'fund_list_sh' / 'fund_list_sz'
            * 'trade_calendar' / 'adj_factor' 等
          调用方必须显式选择正确的 category，上游 bars_recipes / symbol_sync
          已经完成了基于业务语义的分类。

      - freq:
          系统统一频率字符串（可选）：
            '1m','5m','15m','30m','60m','1d','1w','1M'
          仅作为 provider 的输入参数之一：
            - EastMoney K 线适配器：get_kline_em(symbol, freq, end=None, fqt=0)
            - 新浪 K 线适配器：get_kline_sina(symbol, freq, ma="no")
          dispatcher 不在内部根据 freq 做业务决策，不再进行 stock_bars 二级路由。

      - kwargs:
          由上游业务层透传的参数，如：
            symbol='600519', fqt=0/1/2, ma='no', start_date=..., end_date=...
          dispatcher 只负责「基于函数签名进行白名单过滤」，不会修改业务语义。

    返回：
      Tuple[raw_data, method_id]
        - raw_data: 成功时为 DataFrame 或其他原始数据结构，失败时为 None；
        - method_id: 成功方法的全局 ID（如 'eastmoney.stock_daily_kline'），失败时为 None。
    """

    # ===== 1. 规范化 category（当前不再做二级路由）=====
    category = data_category

    # ===== 2. 将 freq 注入 kwargs，供需要它的 provider 使用 =====
    if freq is not None and "freq" not in kwargs:
        kwargs["freq"] = freq

    # ===== 3. 按 category 获取方法列表 =====
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

    # ===== 4. 依次尝试各个方法（按 priority 排序）=====
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
            # ===== 4.1 基于函数签名做参数白名单过滤 =====
            sig = inspect.signature(method.callable)
            accepted_params = set(sig.parameters.keys())

            filtered_kwargs = {
                k: v for k, v in kwargs.items() if k in accepted_params
            }

            if len(filtered_kwargs) < len(kwargs):
                _LOG.debug(
                    f"[参数过滤] {method.id}: 移除 {set(kwargs.keys()) - set(filtered_kwargs.keys())} (函数不接受这些参数)"
                )

            # ===== 4.2 调用 provider 原子函数 =====
            raw_data = await method.callable(**filtered_kwargs)

        except Exception as e:
            exception_caught = e

        # ===== 4.3 使用异常分类器进行精确分类 =====
        error_type, error_message, suggestion = classify_fetch_error(
            exception_caught, raw_data
        )

        # 情况1：成功
        if error_type == "success":
            log_event(
                logger=_LOG,
                service="dispatcher",
                level="INFO",
                event="fetch.success",
                message=f"Method {method.id} succeeded",
                extra={
                    "method_id":
                    method.id,
                    "data_rows":
                    len(raw_data)
                    if isinstance(raw_data, pd.DataFrame)
                    else "N/A",
                },
                file=__file__,
                func="fetch",
                line=0,
                trace_id=None,
            )
            return raw_data, method.id

        # 情况2：返回空数据（非异常）
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

        # 情况3：反爬虫封禁（最严重）
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

            # 发布系统级告警事件（Schema统一）
            from backend.utils.events import publish as publish_event

            publish_event({
                "type": "system_alert",
                "level": "critical",
                "code": "ANTISPIDER_TRIGGERED",
                "message": f"数据源 {method.provider} 的方法 {method.id} 疑似触发反爬虫机制",
                "details": error_message,
                "source": f"dispatcher.{method.provider}",
                "trace_id": None,
                "timestamp": now_iso(),
            })

            last_error = exception_caught
            last_error_type = error_type
            continue

        # 情况4：其他错误
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

    # ===== 5. 所有方法都失败 =====
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