# backend/services/local_import/repository/__init__.py
# ==============================
# 盘后数据导入 import - repository 包统一出口
#
# 职责：
#   - 对外统一导出 local_import 的持久化访问接口
#   - 内部分拆为：
#       * batches.py
#       * tasks.py
#       * common.py
# ==============================

from __future__ import annotations

from .batches import (
    generate_batch_id,
    create_batch_with_tasks,
    get_batch,
    list_all_batches_ordered,
    get_current_running_batch,
    get_first_queued_batch,
    get_last_effective_terminal_batch,
    get_display_batch,
    list_queued_batch_summaries,
    build_status_snapshot,
    mark_batch_running,
    mark_batch_paused,
    recompute_batch_progress_and_state,
    delete_batch_and_tasks,
    delete_all_queued_batches_except,
    promote_first_queued_batch_to_running,
    clear_previous_terminal_batches_except,
)
from .tasks import (
    list_tasks_for_batch,
    get_next_queued_task,
    get_running_task,
    mark_task_running,
    get_task,
    mark_task_terminal,
    cancel_queued_tasks_in_batch,
    reset_retryable_tasks,
    mark_interrupted_running_tasks_failed,
    get_batch_counts,
)

__all__ = [
    "generate_batch_id",
    "create_batch_with_tasks",
    "get_batch",
    "list_all_batches_ordered",
    "get_current_running_batch",
    "get_first_queued_batch",
    "get_last_effective_terminal_batch",
    "get_display_batch",
    "list_queued_batch_summaries",
    "build_status_snapshot",
    "mark_batch_running",
    "mark_batch_paused",
    "recompute_batch_progress_and_state",
    "delete_batch_and_tasks",
    "delete_all_queued_batches_except",
    "promote_first_queued_batch_to_running",
    "clear_previous_terminal_batches_except",

    "list_tasks_for_batch",
    "get_next_queued_task",
    "get_running_task",
    "mark_task_running",
    "get_task",
    "mark_task_terminal",
    "cancel_queued_tasks_in_batch",
    "reset_retryable_tasks",
    "mark_interrupted_running_tasks_failed",
    "get_batch_counts",
]
