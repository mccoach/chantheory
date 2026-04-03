# backend/services/local_import/recovery.py
# ==============================
# 盘后数据导入 import - 启动恢复与一致性清理
#
# 最终规则：
#   - 启动后两张表都必须收敛到“唯一有效批次真相源”
#   - 若正常退出：
#       保留最后一个有效终态批次 + 它的任务
#   - 若异常退出：
#       保留最新 running 批次，修正为 paused + 它的任务
#   - 其他所有批次和任务一律清除
#
# 有效批次优先级：
#   1) 最新 running（异常退出恢复为 paused）
#   2) 最新 paused
#   3) 最新终态（success/failed/cancelled）
#   4) 最新 queued
#
# 本轮 SSE 收敛：
#   - 前端只关心聚合数量，不关心任务明细
#   - recovery 阶段不再逐任务推送 task_changed
#   - 启动恢复完成后只推送一次 local_import.status
# ==============================

from __future__ import annotations

from typing import List, Optional

from backend.services.local_import.repository import (
    get_batches_by_state,
    mark_batch_paused,
    build_status_snapshot,
    delete_batches,
)
from backend.services.local_import.repository.tasks import (
    delete_tasks_except_batch_ids,
    delete_orphan_tasks,
    delete_tasks_for_batch,
    mark_interrupted_running_tasks_failed,
)
from backend.services.local_import.events import emit_local_import_status
from backend.utils.logger import get_logger

_LOG = get_logger("local_import.recovery")


def _emit_status(ui_message: str) -> None:
    snap = build_status_snapshot(ui_message)
    emit_local_import_status(
        display_batch=snap.get("display_batch"),
        queued_batches=snap.get("queued_batches") or [],
        ui_message=snap.get("ui_message"),
    )


def _pick_latest(rows: List[dict]) -> Optional[dict]:
    if not rows:
        return None
    rows_sorted = sorted(rows, key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return rows_sorted[0]


async def recover_interrupted_local_import_batches() -> int:
    """
    启动时执行：
      1) orphan tasks 清理
      2) 确定唯一应保留批次
      3) 其余批次全部删除
      4) tasks 只保留该唯一批次
      5) queued 批次若有 tasks，则清空
      6) 若保留的是 running，则修为 paused + running task -> failed(INTERRUPTED)

    说明：
      - recovery 阶段不再逐任务推送明细事件
      - 所有恢复结果统一收敛为一次 status 推送
    """
    recovered = 0

    delete_orphan_tasks()

    running_batches = get_batches_by_state("running")
    paused_batches = get_batches_by_state("paused")
    success_batches = get_batches_by_state("success")
    failed_batches = get_batches_by_state("failed")
    cancelled_batches = get_batches_by_state("cancelled")
    queued_batches = get_batches_by_state("queued")

    keep_batch = None
    keep_reason = None

    # 1) 若存在 running：按你的规则只保留最新 running
    if running_batches:
        keep_batch = _pick_latest(running_batches)
        keep_reason = "running"

    # 2) 否则若存在 paused：保留最新 paused
    elif paused_batches:
        keep_batch = _pick_latest(paused_batches)
        keep_reason = "paused"

    # 3) 否则若存在终态：保留最新终态
    elif success_batches or failed_batches or cancelled_batches:
        terminal_rows = success_batches + failed_batches + cancelled_batches
        keep_batch = _pick_latest(terminal_rows)
        keep_reason = "terminal"

    # 4) 否则若存在 queued：保留最新 queued
    elif queued_batches:
        keep_batch = _pick_latest(queued_batches)
        keep_reason = "queued"

    # 5) 否则什么都没有，直接返回
    if not keep_batch:
        return recovered

    keep_bid = str(keep_batch["batch_id"])

    # 删除其他所有 batch
    all_batches = (
        running_batches +
        paused_batches +
        success_batches +
        failed_batches +
        cancelled_batches +
        queued_batches
    )
    drop_ids = [
        str(b["batch_id"]) for b in all_batches
        if str(b["batch_id"]) != keep_bid
    ]
    if drop_ids:
        delete_batches(drop_ids)
        _LOG.warning("[LOCAL_IMPORT][RECOVERY] deleted residual batches=%s", drop_ids)

    # tasks 只保留 keep_bid
    delete_tasks_except_batch_ids([keep_bid])

    # 若 keep 是 running，执行异常中断恢复
    if keep_reason == "running":
        # 只做真相源修正，不再逐任务推 SSE
        mark_interrupted_running_tasks_failed(keep_bid)

        mark_batch_paused(
            keep_bid,
            ui_message="导入被异常中断，请检查后重试",
        )
        recovered += 1
        _LOG.warning("[LOCAL_IMPORT][RECOVERY] paused interrupted batch_id=%s", keep_bid)
        _emit_status("导入被异常中断，请检查后重试")
        return recovered

    # 若 keep 是 queued，则它不应有任何 tasks
    if keep_reason == "queued":
        delete_tasks_for_batch(keep_bid)
        _LOG.warning("[LOCAL_IMPORT][RECOVERY] cleared illegal queued-batch tasks batch_id=%s", keep_bid)
        _emit_status("已清理历史残留，仅保留最新排队批次")
        return recovered

    # paused / terminal：保留它和它的任务
    if keep_reason == "paused":
        _emit_status("已恢复最近一次异常中断批次")
    else:
        _emit_status("已恢复最近一次有效完成批次")

    return recovered
