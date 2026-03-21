# backend/services/local_import/orchestrator.py
# ==============================
# 盘后数据导入 import - 串行总编排器
#
# 职责：
#   - 启动批次
#   - 串行推进任务
#   - 保证同一时刻最多一个文件任务 running
#   - 处理 cancel / retry
#   - 在关键状态变化时发 SSE
#
# 关键原则：
#   - SSE 为主链路
#   - HTTP status/tasks 作为初始化、断线恢复和纠偏补充
#   - 单线程顺序执行
#   - 调度依据与 display_batch 展示依据分离
#
# 本次修复：
#   - 修复“新建批次后误跑旧批次”的问题
#   - 修复“单个任务成功后不继续推进下一个 queued 任务”的断链问题
#   - 保证 start 时优先推进当前新建批次
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, List, Optional

from backend.services.local_import.runtime import get_local_import_runtime
from backend.services.local_import.executor import execute_import_file_task
from backend.services.local_import.events import (
    emit_local_import_status,
    emit_local_import_task_changed,
)
from backend.services.local_import.repository import (
    create_batch_with_tasks,
    get_batch,
    get_current_running_batch,
    get_first_queued_batch,
    get_next_queued_task,
    get_running_task,
    build_status_snapshot,
    mark_batch_running,
    mark_task_running,
    mark_task_terminal,
    cancel_queued_tasks_in_batch,
    reset_retryable_tasks,
    recompute_batch_progress_and_state,
    delete_all_queued_batches_except,
    clear_previous_terminal_batches_except,
)
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("local_import.orchestrator")


def _emit_status_snapshot(ui_message: Optional[str] = None) -> Dict[str, Any]:
    snap = build_status_snapshot(ui_message=ui_message)
    emit_local_import_status(
        display_batch=snap.get("display_batch"),
        queued_batches=snap.get("queued_batches") or [],
        ui_message=snap.get("ui_message"),
    )
    return snap


async def _run_single_batch_until_blocked(batch_id: str) -> None:
    """
    串行推进一个 running 批次，直到：
      - 当前批次全部终结
      - 或当前批次不再处于 running
      - 或确有外部并发执行正在持有 running task

    修复点：
      - 不能因为短暂查询到 running 残影，就直接提前结束整批推进
      - 当前 drive_pipeline 已持有 runtime 锁，因此这里应该更偏向“持续推进”
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return

    while True:
        batch = get_batch(bid)
        if not batch:
            return

        state = str(batch.get("state") or "").strip().lower()
        if state != "running":
            return

        # 先查当前是否真的还有 queued 任务
        next_task = get_next_queued_task(bid)

        # 没有 queued 任务：重算批次并结束
        if not next_task:
            recompute_batch_progress_and_state(bid)
            _emit_status_snapshot()
            return

        # 若此时还能看到 running task，说明当前任务可能仍在真正执行中；
        # 这里不立即推进，也不直接把整批永久退出，而是温和返回给上层，
        # 等下一次状态变化或下一次 drive_pipeline 再继续。
        running_task = get_running_task(bid)
        if running_task:
            _LOG.info(
                "[LOCAL_IMPORT] batch=%s temporarily blocked by running task market=%s symbol=%s freq=%s",
                bid,
                running_task.get("market"),
                running_task.get("symbol"),
                running_task.get("freq"),
            )
            return

        market = str(next_task["market"]).strip().upper()
        symbol = str(next_task["symbol"]).strip()
        freq = str(next_task["freq"]).strip()

        runtime = get_local_import_runtime()
        file_path = runtime.get_file_path(market, symbol, freq)
        if not file_path:
            task = mark_task_running(bid, market, symbol, freq)
            if task:
                emit_local_import_task_changed(batch_id=bid, task=task, refresh_tasks=True)

            failed_task = mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "failed",
                "FILE_NOT_FOUND",
                "未能在当前扫描索引中定位到目标本地文件",
            )
            if failed_task:
                emit_local_import_task_changed(batch_id=bid, task=failed_task, refresh_tasks=True)

            recompute_batch_progress_and_state(bid)
            _emit_status_snapshot("导入执行中：存在文件定位失败")
            continue

        task = mark_task_running(bid, market, symbol, freq)
        if task:
            emit_local_import_task_changed(batch_id=bid, task=task, refresh_tasks=True)
        _emit_status_snapshot("正在导入本地盘后文件")

        try:
            await execute_import_file_task(
                batch_id=bid,
                market=market,
                symbol=symbol,
                freq=freq,
                file_path=file_path,
            )
            done_task = mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "success",
                None,
                None,
            )
            if done_task:
                emit_local_import_task_changed(batch_id=bid, task=done_task, refresh_tasks=True)

        except FileNotFoundError as e:
            done_task = mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "failed",
                "FILE_NOT_FOUND",
                str(e),
            )
            if done_task:
                emit_local_import_task_changed(batch_id=bid, task=done_task, refresh_tasks=True)

        except ValueError as e:
            done_task = mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "failed",
                "PARSE_OR_NORMALIZE_FAILED",
                str(e),
            )
            if done_task:
                emit_local_import_task_changed(batch_id=bid, task=done_task, refresh_tasks=True)

        except Exception as e:
            done_task = mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "failed",
                "IMPORT_EXECUTION_FAILED",
                str(e),
            )
            if done_task:
                emit_local_import_task_changed(batch_id=bid, task=done_task, refresh_tasks=True)

        recompute_batch_progress_and_state(bid)
        _emit_status_snapshot()

        # 关键：一个任务终态完成后，继续 while，推进下一个 queued 任务
        await asyncio.sleep(0)


async def _advance_pipeline_if_possible(preferred_batch_id: Optional[str] = None) -> Dict[str, Any]:
    """
    推进整条导入流水线：
      - 调度依据只看：
          * 当前 running batch
          * 最早 queued batch
      - display_batch 只用于展示，不用于调度推进

    preferred_batch_id:
      - start_import_batch 场景下优先推进“当前新建批次”
      - 若该批次还处于 queued，则优先将其提升为 running
    """
    preferred_bid = str(preferred_batch_id or "").strip()

    running = get_current_running_batch()
    if running:
        await _run_single_batch_until_blocked(running["batch_id"])
        return build_status_snapshot()

    if preferred_bid:
        preferred_batch = get_batch(preferred_bid)
        if preferred_batch and str(preferred_batch.get("state") or "").strip().lower() == "queued":
            promoted = mark_batch_running(preferred_bid)
            if promoted:
                clear_previous_terminal_batches_except(promoted["batch_id"])
                _emit_status_snapshot("正在导入本地盘后文件")
                await _run_single_batch_until_blocked(promoted["batch_id"])
                return build_status_snapshot()

    first_queued = get_first_queued_batch()
    if first_queued:
        promoted = mark_batch_running(first_queued["batch_id"])
        if promoted:
            clear_previous_terminal_batches_except(promoted["batch_id"])
            _emit_status_snapshot("正在导入本地盘后文件")
            await _run_single_batch_until_blocked(promoted["batch_id"])
        return build_status_snapshot()

    return build_status_snapshot()


async def start_import_batch(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    创建新导入批次并尝试推进流水线。

    修复点：
      - 新批次创建后，优先推进当前新建批次
      - 避免误跑历史 queued 批次
    """
    runtime = get_local_import_runtime()
    runtime.refresh_scan_cache()

    batch = create_batch_with_tasks(items)
    new_batch_id = batch["batch_id"]

    log_event(
        logger=_LOG,
        service="local_import.orchestrator",
        level="INFO",
        file=__file__,
        func="start_import_batch",
        line=0,
        trace_id=None,
        event="local_import.batch.created",
        message="local import batch created",
        extra={
            "batch_id": new_batch_id,
            "items_count": len(items),
        },
    )

    _emit_status_snapshot("已创建导入批次")

    if not runtime.is_locked():
        await drive_pipeline(preferred_batch_id=new_batch_id)

    return build_status_snapshot("已创建导入批次")


async def cancel_import_batch(batch_id: str) -> Dict[str, Any]:
    """
    取消当前有效批次及其后所有尚未有效进入的 queued 批次。

    语义：
      - 当前 running task 不杀
      - 当前批次其余 queued task -> cancelled
      - 所有后续 queued 批次直接删除
      - 对真正发生 queued->cancelled 的任务逐条发 task_changed
    """
    bid = str(batch_id or "").strip()
    batch = get_batch(bid)
    if not batch:
        return build_status_snapshot("未找到要取消的批次")

    state = str(batch.get("state") or "").strip().lower()
    if state not in ("queued", "running"):
        return build_status_snapshot("当前批次不可取消")

    changed_tasks = cancel_queued_tasks_in_batch(bid)
    for task in changed_tasks:
        emit_local_import_task_changed(
            batch_id=bid,
            task=task,
            refresh_tasks=True,
        )

    delete_all_queued_batches_except(bid)

    recompute_batch_progress_and_state(
        bid,
        ui_message="取消已提交：当前正在导入的文件会执行完，未开始任务将被取消",
    )

    snap = _emit_status_snapshot("取消已提交：当前正在导入的文件会执行完，未开始任务将被取消")

    runtime = get_local_import_runtime()
    if not runtime.is_locked():
        await drive_pipeline()

    return snap


async def retry_import_batch(batch_id: str) -> Dict[str, Any]:
    """
    retry 语义：
      - success 不重跑
      - failed -> queued
      - cancelled -> queued

    只对真正发生状态变化的任务逐条发 task_changed。
    """
    bid = str(batch_id or "").strip()
    batch = get_batch(bid)
    if not batch:
        return build_status_snapshot("未找到要重试的批次")

    state = str(batch.get("state") or "").strip().lower()
    if state not in ("failed", "cancelled", "paused"):
        return build_status_snapshot("当前批次不可重试")

    changed_tasks = reset_retryable_tasks(bid)
    recompute_batch_progress_and_state(
        bid,
        ui_message="已重新加入失败/已取消任务，成功任务不会重复导入",
    )

    for task in changed_tasks:
        emit_local_import_task_changed(
            batch_id=bid,
            task=task,
            refresh_tasks=True,
        )

    snap = _emit_status_snapshot("已重新加入失败/已取消任务，成功任务不会重复导入")

    runtime = get_local_import_runtime()
    if not runtime.is_locked():
        await drive_pipeline(preferred_batch_id=bid)

    return snap


async def drive_pipeline(preferred_batch_id: Optional[str] = None) -> Dict[str, Any]:
    """
    串行驱动入口。
    保证同一时刻只有一个调度循环在推进。
    """
    runtime = get_local_import_runtime()

    await runtime.lock()
    try:
        runtime.refresh_scan_cache()
        snap = await _advance_pipeline_if_possible(preferred_batch_id=preferred_batch_id)
        return snap
    finally:
        runtime.unlock()
