# backend/utils/async_retry.py
# ==============================
# 说明：异步版本的统一重试工具（全新模块）
# - 职责：为异步函数提供指数退避重试能力。
# - 设计：与同步版 `retry.py` 保持相同的接口风格，但使用 `asyncio.sleep` 替代 `time.sleep`。
# ==============================

from __future__ import annotations

import asyncio
import random
from typing import Callable, Any, Optional, Awaitable

try:
    import httpx
except ImportError:
    httpx = None

from backend.utils.logger import get_logger, log_event
from backend.utils.events import publish as publish_event
from backend.settings import settings

_LOG = get_logger("async_retry")

async def async_retry_call(
    fn: Callable[[], Awaitable[Any]],
    attempts: Optional[int] = None,
    base_delay_ms: Optional[int] = None
) -> Any:
    """
    异步版本的可重试调用（指数退避 + 随机抖动）。
    
    Args:
        fn: 要执行的无参异步函数（返回 Awaitable）。
        attempts: 最大重试次数。如果为 None，则从 settings 读取。
        base_delay_ms: 基础延迟毫秒数。如果为 None，则从 settings 读取。

    Returns:
        fn() 的执行结果。

    Raises:
        如果所有尝试都失败，则抛出最后一次的异常。
    """
    max_attempts = int(attempts if attempts is not None else settings.retry_max_attempts)
    delay_ms = int(base_delay_ms if base_delay_ms is not None else settings.retry_base_delay_ms)
    
    last_exc = None
    for i in range(max_attempts + 1):
        try:
            return await fn()
        except Exception as e:
            last_exc = e

            # 检查是否为疑似反爬虫的特定网络异常
            is_antispider_error = False
            if httpx and isinstance(e, (httpx.RemoteProtocolError, httpx.ConnectError)):
                is_antispider_error = True

            if is_antispider_error:
                log_event(
                    logger=_LOG, service="async_retry", level="CRITICAL",
                    file=__file__, func="async_retry_call", line=0, trace_id=None,
                    event="antispider.triggered",
                    message="Potential anti-spider mechanism triggered.",
                    extra={"error_message": str(e)}
                )
                publish_event({
                    "type": "system_alert", "level": "error",
                    "code": "ANTISPIDER_TRIGGERED",
                    "message": "网络请求被远程主机关闭，可能触发了反爬虫策略。",
                    "details": str(e)
                })

            if i >= max_attempts:
                break
            
            # 计算延迟时间（秒）
            delay = (delay_ms / 1000.0) * (2 ** i)
            # 添加抖动 (0.8 ~ 1.2倍)
            jittered_delay = delay * (0.8 + 0.4 * random.random())
            
            await asyncio.sleep(jittered_delay)
            
    if last_exc is not None:
        raise last_exc
    
    return None
