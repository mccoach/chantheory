# backend/utils/alerts.py
# ==============================
# 说明：系统告警统一出口（V1.0）
#
# 目标：
#   - 将系统级告警(system_alert)的 schema 构造与 publish 行为收敛为唯一出口；
#   - 避免 dispatcher / retry / async_retry 等模块各自拼装 schema 导致重复与不一致；
#   - 上游只需调用 emit_system_alert(...)，下游通过 utils.events → SSE 桥接统一推送。
#
# Schema（统一）：
#   {
#     "type": "system.alert",
#     "level": "error" | "critical" | ...,
#     "code": "ANTISPIDER_TRIGGERED" | ...,
#     "message": "...",
#     "details": "...",
#     "source": "dispatcher.<provider>" | "async_retry" | ...,
#     "trace_id": null | "...",
#     "timestamp": "ISO8601"
#   }
# ==============================

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.utils.events import publish as publish_event
from backend.utils.time import now_iso


def emit_system_alert(
    *,
    level: str,
    code: str,
    message: str,
    details: Optional[str] = None,
    source: str,
    trace_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    发布 system_alert 事件（统一 schema）。

    Args:
        level: 告警等级，如 "error"/"critical"
        code:  告警码，如 "ANTISPIDER_TRIGGERED"
        message: 告警摘要
        details: 详细信息（可为空）
        source: 来源模块标识（必须显式传入，避免猜测）
        trace_id: 追踪ID（可选）
        extra: 额外字段（可选，尽量保持小体积）

    Returns:
        Dict[str, Any]: 已发布的事件对象（便于测试或上层日志记录）
    """
    event: Dict[str, Any] = {
        "type": "system.alert",
        "level": str(level or "").strip() or "error",
        "code": str(code or "").strip() or "UNKNOWN",
        "message": str(message or "").strip() or "",
        "details": str(details) if details is not None else None,
        "source": str(source or "").strip() or "unknown",
        "trace_id": trace_id,
        "timestamp": now_iso(),
        "extra": extra if isinstance(extra, dict) else {},
    }

    publish_event(event)
    return event
