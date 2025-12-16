# backend/utils/retry.py
# ==============================
# 说明：统一的重试工具（同步版）
# - (NEW) 增加对特定网络异常的捕获，并触发日志和SSE告警事件。
#
# 改动（Schema统一）：
#   - system_alert 事件统一为：
#       {
#         "type": "system_alert",
#         "level": "error" | "critical" | ...,
#         "code": "ANTISPIDER_TRIGGERED" | ...,
#         "message": "...",
#         "details": "...",
#         "source": "retry",
#         "trace_id": null | "...",
#         "timestamp": "ISO8601"
#       }
# ==============================

from __future__ import annotations

import time
import random
from typing import Callable, Any, Optional

try:
    import httpx
except ImportError:
    httpx = None

from backend.utils.logger import get_logger, log_event
from backend.utils.events import publish as publish_event
from backend.settings import settings
from backend.utils.time import now_iso

_LOG = get_logger("retry")


def retry_call(
    fn: Callable[[], Any],
    attempts: Optional[int] = None,
    base_delay_ms: Optional[int] = None
) -> Any:
    """
    可重试调用（指数退避 + 随机抖动）。
    - fn: 要执行的无参函数。
    - attempts: 最大重试次数。如果为None，则从 settings 读取。
    - base_delay_ms: 基础延迟毫秒数。如果为None，则从 settings 读取。
    """
    max_attempts = int(attempts if attempts is not None else settings.retry_max_attempts)
    delay_ms = int(base_delay_ms if base_delay_ms is not None else settings.retry_base_delay_ms)

    last_exc = None
    for i in range(max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e

            # (NEW) 检查是否为疑似反爬虫的特定网络异常
            is_antispider_error = False
            if httpx and isinstance(e, (httpx.RemoteProtocolError, httpx.ConnectError)):
                is_antispider_error = True

            if is_antispider_error:
                # 记录CRITICAL日志
                log_event(
                    logger=_LOG,
                    service="retry",
                    level="CRITICAL",
                    file=__file__, func="retry_call", line=0, trace_id=None,
                    event="antispider.triggered",
                    message="Potential anti-spider mechanism triggered. Connection closed by remote host.",
                    extra={"error_message": str(e)}
                )
                # 推送SSE告警事件
                publish_event({
                    "type": "system_alert",
                    "level": "error",
                    "code": "ANTISPIDER_TRIGGERED",
                    "message": "网络请求被远程主机关闭，可能触发了数据源反爬虫策略，数据同步将受影响。",
                    "details": str(e),
                    "source": "retry",
                    "trace_id": None,
                    "timestamp": now_iso(),
                })

            if i >= max_attempts:
                break

            # 计算延迟时间（秒）
            delay = (delay_ms / 1000.0) * (2 ** i)
            # 添加抖动 (0.8 ~ 1.2倍)
            jittered_delay = delay * (0.8 + 0.4 * random.random())

            time.sleep(jittered_delay)

    if last_exc is not None:
        raise last_exc

    # 理论上不应该到达这里
    return None