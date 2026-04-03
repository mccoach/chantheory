# backend/services/local_import/events.py
# ==============================
# 盘后数据导入 import - SSE 事件统一出口
#
# 当前最终收敛模型：
#   - local_import 只保留一种 SSE：
#       1) local_import.status
#          * 主界面唯一实时真相事件
#          * 由“批次元信息 + tasks 聚合进度”统一构造后发出
#
# 设计原则（本轮重构）：
#   - 前端只关心数量变化，不关心单任务明细
#   - 后端聚合数值是唯一真相源
#   - 批量状态瞬变（start/cancel/retry/批次收敛）统一收敛成一次 status 推送
#   - 单个任务真实完成/失败时，再逐次推送 status，以体现实时进度跳变
#
# 明确删除：
#   - local_import.task_changed
#   - 一切逐任务明细型 SSE 冗余路径
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
