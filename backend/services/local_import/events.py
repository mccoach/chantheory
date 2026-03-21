# backend/services/local_import/events.py
# ==============================
# 盘后数据导入 import - SSE 事件统一出口
#
# 冻结事件：
#   1) local_import.status
#      - 主界面真相源
#      - 直接携带 display_batch / queued_batches / ui_message
#
#   2) local_import.task_changed
#      - 任务表变化事件
#      - 携带 batch_id / task / refresh_tasks
#
# 说明：
#   - SSE 是本地导入主状态同步链路
#   - HTTP status/tasks 只做初始化、断线恢复和纠偏补充
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional

from backend.utils.events import publish as publish_event
from backend.utils.time import now_iso


def emit_local_import_status(
    *,
    display_batch: Optional[Dict[str, Any]],
    queued_batches: list[Dict[str, Any]],
    ui_message: Optional[str],
) -> Dict[str, Any]:
    event = {
        "type": "local_import.status",
        "display_batch": display_batch,
        "queued_batches": queued_batches,
        "ui_message": ui_message,
        "timestamp": now_iso(),
    }
    publish_event(event)
    return event


def emit_local_import_task_changed(
    *,
    batch_id: str,
    task: Dict[str, Any],
    refresh_tasks: bool = True,
) -> Dict[str, Any]:
    event = {
        "type": "local_import.task_changed",
        "batch_id": str(batch_id or "").strip(),
        "task": dict(task or {}),
        "refresh_tasks": bool(refresh_tasks),
        "timestamp": now_iso(),
    }
    publish_event(event)
    return event
