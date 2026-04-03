# backend/services/basic_data_status.py
# ==============================
# 基础数据任务稳定状态服务
#
# 职责：
#   - 聚合基础数据任务的稳定状态
#   - 对外提供统一只读视图
#   - 对内允许 idle 细分
#
# 当前任务范围：
#   - symbol_index
#   - profile_snapshot
#   - trade_calendar
#   - factor_events_snapshot
# ==============================

from __future__ import annotations

from typing import Dict, Any, List

from backend.db.data_task_status import (
    select_all_data_task_status,
)

_TASK_TYPES = [
    "symbol_index",
    "profile_snapshot",
    "trade_calendar",
    "factor_events_snapshot",
]


def _default_status(task_type: str) -> Dict[str, Any]:
    return {
        "task_type": task_type,
        "task_status": "idle",
        "idle_reason": "never_executed",
        "last_success_at": None,
        "last_failure_at": None,
        "last_error_message": None,
        "updated_at": None,
    }


def get_basic_data_status_snapshot() -> Dict[str, Any]:
    rows = select_all_data_task_status()
    mapping = {
        str(r.get("task_type") or "").strip(): dict(r)
        for r in rows
        if isinstance(r, dict) and str(r.get("task_type") or "").strip()
    }

    items: List[Dict[str, Any]] = []
    for task_type in _TASK_TYPES:
        row = mapping.get(task_type) or _default_status(task_type)
        items.append({
            "task_type": task_type,
            "task_status": row.get("task_status") or "idle",
            "last_success_at": row.get("last_success_at"),
            "last_failure_at": row.get("last_failure_at"),
            "last_error_message": row.get("last_error_message"),
            "idle_reason": row.get("idle_reason"),
            "updated_at": row.get("updated_at"),
        })

    return {
        "ok": True,
        "items": items,
    }
