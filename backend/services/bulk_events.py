# backend/services/bulk_events.py
# ==============================
# After Hours Bulk v2.2
#
# 职责：
#   - 发布 bulk_batch_snapshot SSE 事件（必须通过既有 /api/events/stream 通道）
#   - schema 写死：
#       event.type = "bulk_batch_snapshot"
#       data = { backend_instance_id, batch }
# 统一事件：
#   - bulk.batch.snapshot
# ==============================

from __future__ import annotations

from typing import Dict, Any
from backend.utils.events import publish as publish_event
from backend.services.server_identity import get_backend_instance_id


def emit_bulk_batch_snapshot(batch_snapshot: Dict[str, Any]) -> None:
    event = {
        "type": "bulk.batch.snapshot",
        "backend_instance_id": get_backend_instance_id(),
        "batch": batch_snapshot,
    }
    publish_event(event)
