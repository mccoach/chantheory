# backend/services/local_import/recovery.py
# ==============================
# 盘后数据导入 import - 启动恢复链路
#
# 职责：
#   - 服务启动时检查是否存在“上次异常中断的 running 批次”
#   - 若存在：
#       * running batch -> paused
#       * running tasks -> failed(INTERRUPTED)
#   - 发出对应 SSE 状态快照与任务变更事件
#
# 设计原则：
#   - paused 只用于系统被动中断
#   - 不开放用户 pause/resume
# ==============================

from __future__ import annotations

from backend.services.local_import.repository import (
    mark_batch_paused,
    recompute_batch_progress_and_state,
    get_current_running_batch,
)
from backend.services.local_import.repository.tasks import (
    mark_interrupted_running_tasks_failed,
)
from backend.services.local_import.events import (
    emit_local_import_status,
    emit_local_import_task_changed,
)
from backend.services.local_import.repository.batches import build_status_snapshot
from backend.utils.logger import get_logger

_LOG = get_logger("local_import.recovery")


async def recover_interrupted_local_import_batches() -> int:
    """
    恢复被异常中断的 local-import 批次。

    规则：
      - 仅处理 state='running' 的批次
      - 先将其 running task 纠偏为 failed(INTERRUPTED)
      - 再将 batch 标记为 paused
      - 之后重算进度（paused 状态保留，不自动转 terminal）
    """
    recovered = 0

    while True:
        running = get_current_running_batch()
        if not running:
            break

        bid = running["batch_id"]

        changed_tasks = mark_interrupted_running_tasks_failed(bid)
        for task in changed_tasks:
            emit_local_import_task_changed(
                batch_id=bid,
                task=task,
                refresh_tasks=True,
            )

        mark_batch_paused(
            bid,
            ui_message="导入被异常中断，请检查后重试",
        )

        recompute_batch_progress_and_state(
            bid,
            ui_message="导入被异常中断，请检查后重试",
        )

        snap = build_status_snapshot("导入被异常中断，请检查后重试")
        emit_local_import_status(
            display_batch=snap.get("display_batch"),
            queued_batches=snap.get("queued_batches") or [],
            ui_message=snap.get("ui_message"),
        )

        recovered += 1
        _LOG.warning("[LOCAL_IMPORT][RECOVERY] paused interrupted batch_id=%s", bid)

        # mark_batch_paused 后 current_running_batch 应该消失；
        # while 循环继续检查是否还有其他残留 running 批次
    return recovered
