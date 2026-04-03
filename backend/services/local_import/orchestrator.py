# backend/services/local_import/orchestrator.py
# ==============================
# 盘后数据导入 import - 串行总编排器
#
# 职责（修复后）：
#   - 只负责流程编排
#   - 不再负责 display/status 视图构造
#   - 不再直接解释 progress
#
# 真相源收敛：
#   - 候选结果真相源：本地持久化候选结果文件
#   - 执行真相源：local_import_tasks
#   - 批次表：只保留元信息与调度状态
#   - 对前端展示视图统一由 repository.build_status_snapshot() 构造
#
# 本轮改动（refresh / get 拆分版）：
#   - orchestrator / pipeline 不再消费 runtime 内存扫描快照
#   - 统一只消费本地持久化候选结果真相源
# ==============================

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Dict, Any, List, Optional

from backend.services.local_import.runtime import get_local_import_runtime
from backend.services.local_import.executor import execute_import_file_task
from backend.services.local_import.events import emit_local_import_status
from backend.services.local_import.repository import (
    create_batch,
    get_batch,
    list_all_batches_ordered,
    get_current_running_batch,
    get_oldest_queued_batch,
    get_next_queued_task,
    get_running_task,
    get_latest_active_batch_by_signature,
    build_status_snapshot,
    mark_batch_running,
    mark_batch_paused,
    mark_batch_queued_for_retry,
    mark_batch_terminal_state,
    update_batch_ui_message,
    mark_task_running,
    mark_task_terminal,
    cancel_queued_tasks_in_batch,
    reset_retryable_tasks,
    create_tasks_for_batch,
    list_tasks_for_batch,
    delete_batches,
    get_batch_counts,
)
from backend.services.local_import.repository.tasks import (
    delete_tasks_except_batch_ids,
)
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("local_import.orchestrator")


def _ms(start_ts: float) -> int:
    return int((time.perf_counter() - start_ts) * 1000)


def _log_stage(stage: str, start_ts: float, **extra: Any) -> None:
    payload = {"elapsed_ms": _ms(start_ts)}
    payload.update(extra)
    _LOG.info("[LOCAL_IMPORT][TIMING] stage=%s payload=%s", stage, payload)


def _emit_status_snapshot(ui_message: Optional[str] = None) -> Dict[str, Any]:
    snap = build_status_snapshot(ui_message=ui_message)
    emit_local_import_status(
        display_batch=snap.get("display_batch"),
        queued_batches=snap.get("queued_batches") or [],
        ui_message=snap.get("ui_message"),
    )
    return snap


def _normalize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for item in items or []:
        market = str(item.get("market") or "").strip().upper()
        symbol = str(item.get("symbol") or "").strip()
        freq = str(item.get("freq") or "").strip()
        if market not in ("SH", "SZ", "BJ") or not symbol or not freq:
            continue
        out.append({
            "market": market,
            "symbol": symbol,
            "freq": freq,
        })
    out.sort(key=lambda x: (x["market"], x["symbol"], x["freq"]))
    return out


def _build_selection_signature(items: List[Dict[str, Any]]) -> str:
    norm = _normalize_items(items)
    raw = json.dumps(norm, ensure_ascii=False, separators=(",", ":"))
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def _delete_all_batches_except(keep_batch_id: str) -> None:
    keep_bid = str(keep_batch_id or "").strip()
    if not keep_bid:
        return

    all_batches = list_all_batches_ordered()
    drop_ids = [
        str(b["batch_id"]) for b in all_batches
        if str(b["batch_id"]) != keep_bid
    ]
    if drop_ids:
        delete_batches(drop_ids)
    delete_tasks_except_batch_ids([keep_bid])


def _settle_batch_state_from_tasks(batch_id: str, ui_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
    batch = get_batch(batch_id)
    if not batch:
        return None

    old_state = str(batch.get("state") or "").strip().lower()
    if old_state == "paused":
        if ui_message is not None:
            return update_batch_ui_message(batch_id, ui_message)
        return batch

    queued_count, running_count, success_count, failed_count, cancelled_count = get_batch_counts(batch_id)
    total = queued_count + running_count + success_count + failed_count + cancelled_count
    done = success_count + failed_count + cancelled_count

    if old_state == "queued" and not batch.get("started_at"):
        if ui_message is not None:
            return update_batch_ui_message(batch_id, ui_message)
        return batch

    if done < total:
        b = get_batch(batch_id)
        if b and str(b.get("state") or "").strip().lower() != "running":
            mark_batch_running(batch_id, ui_message or "正在导入本地盘后文件")
            return get_batch(batch_id)

        if ui_message is not None:
            return update_batch_ui_message(batch_id, ui_message)
        return get_batch(batch_id)

    if cancelled_count > 0:
        return mark_batch_terminal_state(
            batch_id,
            "cancelled",
            ui_message or "导入已结束：存在已取消任务",
        )
    if failed_count > 0:
        return mark_batch_terminal_state(
            batch_id,
            "failed",
            ui_message or "导入已结束：存在失败任务",
        )
    return mark_batch_terminal_state(
        batch_id,
        "success",
        ui_message or "导入完成",
    )


async def _run_single_batch_until_blocked(
    batch_id: str,
    trigger: str = "unknown",
    pipeline_start_ts: Optional[float] = None,
) -> None:
    bid = str(batch_id or "").strip()
    if not bid:
        return

    first_task_running_logged = False
    first_task_finished_logged = False

    while True:
        batch = get_batch(bid)
        if not batch:
            if pipeline_start_ts is not None:
                _log_stage(
                    "pipeline.batch_missing",
                    pipeline_start_ts,
                    trigger=trigger,
                    batch_id=bid,
                )
            return

        state = str(batch.get("state") or "").strip().lower()
        if state != "running":
            if pipeline_start_ts is not None:
                _log_stage(
                    "pipeline.batch_not_running_stop",
                    pipeline_start_ts,
                    trigger=trigger,
                    batch_id=bid,
                    state=state,
                )
            return

        next_task = get_next_queued_task(bid)
        if not next_task:
            _settle_batch_state_from_tasks(bid)
            _emit_status_snapshot()
            if pipeline_start_ts is not None:
                _log_stage(
                    "pipeline.no_more_queued_tasks",
                    pipeline_start_ts,
                    trigger=trigger,
                    batch_id=bid,
                )
            return

        running_task = get_running_task(bid)
        if running_task:
            if pipeline_start_ts is not None:
                _log_stage(
                    "pipeline.blocked_by_existing_running_task",
                    pipeline_start_ts,
                    trigger=trigger,
                    batch_id=bid,
                    running_market=running_task.get("market"),
                    running_symbol=running_task.get("symbol"),
                    running_freq=running_task.get("freq"),
                )
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
            mark_task_running(bid, market, symbol, freq)

            mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "failed",
                "FILE_NOT_FOUND",
                "未能在当前候选结果真相源中定位到目标本地文件",
                None,
                None,
            )

            _settle_batch_state_from_tasks(bid, "导入执行中：存在文件定位失败")
            _emit_status_snapshot("导入执行中：存在文件定位失败")

            if pipeline_start_ts is not None and not first_task_finished_logged:
                first_task_finished_logged = True
                _log_stage(
                    "pipeline.first_task_finished",
                    pipeline_start_ts,
                    trigger=trigger,
                    batch_id=bid,
                    market=market,
                    symbol=symbol,
                    freq=freq,
                    result="failed",
                    signal_code="FILE_NOT_FOUND",
                )
            continue

        mark_task_running(bid, market, symbol, freq)

        if pipeline_start_ts is not None and not first_task_running_logged:
            first_task_running_logged = True
            _log_stage(
                "pipeline.first_task_running",
                pipeline_start_ts,
                trigger=trigger,
                batch_id=bid,
                market=market,
                symbol=symbol,
                freq=freq,
            )

        try:
            result = await execute_import_file_task(
                batch_id=bid,
                market=market,
                symbol=symbol,
                freq=freq,
                file_path=file_path,
            )

            signal_code = result.get("signal_code")
            signal_message = result.get("signal_message")
            appended_rows = result.get("appended_rows")
            source_file_path = result.get("source_file_path")

            mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "success",
                signal_code,
                signal_message,
                appended_rows,
                source_file_path,
            )

            if signal_code and signal_message:
                _settle_batch_state_from_tasks(bid, signal_message)
                _emit_status_snapshot(signal_message)
            else:
                _settle_batch_state_from_tasks(bid)
                _emit_status_snapshot()

            if pipeline_start_ts is not None and not first_task_finished_logged:
                first_task_finished_logged = True
                _log_stage(
                    "pipeline.first_task_finished",
                    pipeline_start_ts,
                    trigger=trigger,
                    batch_id=bid,
                    market=market,
                    symbol=symbol,
                    freq=freq,
                    result="success",
                    signal_code=signal_code,
                )

        except FileNotFoundError as e:
            mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "failed",
                "FILE_NOT_FOUND",
                str(e),
                None,
                file_path,
            )

            _settle_batch_state_from_tasks(bid)
            _emit_status_snapshot()

            if pipeline_start_ts is not None and not first_task_finished_logged:
                first_task_finished_logged = True
                _log_stage(
                    "pipeline.first_task_finished",
                    pipeline_start_ts,
                    trigger=trigger,
                    batch_id=bid,
                    market=market,
                    symbol=symbol,
                    freq=freq,
                    result="failed",
                    signal_code="FILE_NOT_FOUND",
                )

        except ValueError as e:
            msg = str(e)
            signal_code = "PARSE_OR_NORMALIZE_FAILED"

            mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "failed",
                signal_code,
                msg,
                None,
                file_path,
            )

            _settle_batch_state_from_tasks(bid)
            _emit_status_snapshot()

            if pipeline_start_ts is not None and not first_task_finished_logged:
                first_task_finished_logged = True
                _log_stage(
                    "pipeline.first_task_finished",
                    pipeline_start_ts,
                    trigger=trigger,
                    batch_id=bid,
                    market=market,
                    symbol=symbol,
                    freq=freq,
                    result="failed",
                    signal_code=signal_code,
                )

        except Exception as e:
            mark_task_terminal(
                bid,
                market,
                symbol,
                freq,
                "failed",
                "IMPORT_EXECUTION_FAILED",
                str(e),
                None,
                file_path,
            )

            _settle_batch_state_from_tasks(bid)
            _emit_status_snapshot()

            if pipeline_start_ts is not None and not first_task_finished_logged:
                first_task_finished_logged = True
                _log_stage(
                    "pipeline.first_task_finished",
                    pipeline_start_ts,
                    trigger=trigger,
                    batch_id=bid,
                    market=market,
                    symbol=symbol,
                    freq=freq,
                    result="failed",
                    signal_code="IMPORT_EXECUTION_FAILED",
                )

        await asyncio.sleep(0)


async def _promote_batch_to_running_if_possible(
    batch_id: str,
    items: List[Dict[str, Any]],
    trigger: str = "unknown",
    pipeline_start_ts: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    if not bid:
        return None

    promoted = mark_batch_running(bid)
    if not promoted:
        if pipeline_start_ts is not None:
            _log_stage(
                "pipeline.promote_skipped",
                pipeline_start_ts,
                trigger=trigger,
                batch_id=bid,
            )
        return None

    if pipeline_start_ts is not None:
        _log_stage(
            "pipeline.batch_promoted_running",
            pipeline_start_ts,
            trigger=trigger,
            batch_id=bid,
        )

    create_tasks_for_batch(bid, _normalize_items(items))
    _settle_batch_state_from_tasks(bid, "正在导入本地盘后文件")

    if pipeline_start_ts is not None:
        _log_stage(
            "pipeline.tasks_created",
            pipeline_start_ts,
            trigger=trigger,
            batch_id=bid,
            items_count=len(items or []),
        )

    _emit_status_snapshot("正在导入本地盘后文件")
    if pipeline_start_ts is not None:
        _log_stage(
            "pipeline.first_running_status_emitted",
            pipeline_start_ts,
            trigger=trigger,
            batch_id=bid,
        )

    return get_batch(bid)


async def _advance_pipeline_if_possible(
    preferred_batch_id: Optional[str] = None,
    preferred_items: Optional[List[Dict[str, Any]]] = None,
    trigger: str = "unknown",
    pipeline_start_ts: Optional[float] = None,
) -> Dict[str, Any]:
    if pipeline_start_ts is not None:
        _log_stage(
            "pipeline.advance_begin",
            pipeline_start_ts,
            trigger=trigger,
            preferred_batch_id=preferred_batch_id,
            preferred_items_count=len(preferred_items or []),
        )

    running = get_current_running_batch()
    if running:
        if pipeline_start_ts is not None:
            _log_stage(
                "pipeline.use_existing_running_batch",
                pipeline_start_ts,
                trigger=trigger,
                batch_id=running["batch_id"],
            )
        await _run_single_batch_until_blocked(
            running["batch_id"],
            trigger=trigger,
            pipeline_start_ts=pipeline_start_ts,
        )
        return build_status_snapshot()

    preferred_bid = str(preferred_batch_id or "").strip()
    if preferred_bid and preferred_items:
        preferred = get_batch(preferred_bid)
        if preferred and str(preferred.get("state") or "").strip().lower() == "queued":
            promoted = await _promote_batch_to_running_if_possible(
                preferred_bid,
                preferred_items,
                trigger=trigger,
                pipeline_start_ts=pipeline_start_ts,
            )
            if promoted:
                await _run_single_batch_until_blocked(
                    promoted["batch_id"],
                    trigger=trigger,
                    pipeline_start_ts=pipeline_start_ts,
                )
                return build_status_snapshot()

    oldest_queued = get_oldest_queued_batch()
    if oldest_queued:
        queued_bid = oldest_queued["batch_id"]
        if pipeline_start_ts is not None:
            _log_stage(
                "pipeline.queued_without_items_context",
                pipeline_start_ts,
                trigger=trigger,
                batch_id=queued_bid,
            )
        _LOG.warning(
            "[LOCAL_IMPORT] found queued batch without explicit items injection, waiting for explicit start/retry batch_id=%s",
            queued_bid
        )
        return build_status_snapshot("存在排队批次，但缺少显式任务展开上下文，请重新发起开始/重试")

    if pipeline_start_ts is not None:
        _log_stage(
            "pipeline.nothing_to_do",
            pipeline_start_ts,
            trigger=trigger,
        )

    return build_status_snapshot()


def _schedule_drive_pipeline(
    preferred_batch_id: Optional[str] = None,
    preferred_items: Optional[List[Dict[str, Any]]] = None,
    trigger: str = "unknown",
) -> None:
    schedule_ts = time.perf_counter()
    _log_stage(
        "pipeline.scheduled",
        schedule_ts,
        trigger=trigger,
        preferred_batch_id=preferred_batch_id,
        preferred_items_count=len(preferred_items or []),
    )

    async def _runner() -> None:
        runner_ts = time.perf_counter()
        _log_stage(
            "pipeline.runner_started",
            runner_ts,
            trigger=trigger,
            preferred_batch_id=preferred_batch_id,
        )
        try:
            await drive_pipeline(
                preferred_batch_id=preferred_batch_id,
                preferred_items=preferred_items,
                trigger=trigger,
                scheduled_at=schedule_ts,
            )
        except Exception as e:
            _LOG.exception("[LOCAL_IMPORT] background drive_pipeline failed: %s", e)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_runner())
    except RuntimeError:
        _LOG.exception("[LOCAL_IMPORT] failed to schedule background pipeline: no running event loop")


async def start_import_batch(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    req_ts = time.perf_counter()
    _log_stage("start.request_received", req_ts, items_count=len(items or []))

    norm_items = _normalize_items(items)
    _log_stage("start.items_normalized", req_ts, normalized_items_count=len(norm_items))

    if not norm_items:
        _log_stage("start.invalid_no_items", req_ts)
        return build_status_snapshot("未提供有效导入项")

    signature = _build_selection_signature(norm_items)
    _log_stage("start.signature_built", req_ts, selection_signature=signature)

    existing = get_latest_active_batch_by_signature(signature)
    if existing:
        _LOG.warning(
            "[LOCAL_IMPORT] duplicate start ignored batch_id=%s signature=%s state=%s",
            existing["batch_id"],
            signature,
            existing["state"],
        )
        _log_stage(
            "start.duplicate_ignored",
            req_ts,
            batch_id=existing["batch_id"],
            state=existing["state"],
        )
        return build_status_snapshot("当前勾选范围未变化，不能重复开始导入")

    runtime = get_local_import_runtime()

    _log_stage("start.before_require_persisted_snapshot", req_ts)
    try:
        snapshot = runtime.require_persisted_snapshot()
    except Exception:
        _log_stage("start.persisted_snapshot_missing", req_ts)
        return build_status_snapshot("当前没有可用候选结果，请先刷新候选")

    _log_stage(
        "start.after_require_persisted_snapshot",
        req_ts,
        snapshot_generated_at=snapshot.get("generated_at"),
        snapshot_items_count=len(snapshot.get("items") or []),
    )

    batch = create_batch(
        selection_signature=signature,
        item_count=len(norm_items),
    )
    new_batch_id = batch["batch_id"]
    _log_stage("start.batch_created", req_ts, batch_id=new_batch_id)

    _delete_all_batches_except(new_batch_id)
    _log_stage("start.old_batches_cleaned", req_ts, keep_batch_id=new_batch_id)

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
            "items_count": len(norm_items),
            "selection_signature": signature,
        },
    )

    snap = _emit_status_snapshot("批次已启动，正在准备导入任务")
    _log_stage("start.first_status_emitted", req_ts, batch_id=new_batch_id)

    _schedule_drive_pipeline(
        preferred_batch_id=new_batch_id,
        preferred_items=norm_items,
        trigger="start",
    )
    _log_stage("start.background_pipeline_scheduled", req_ts, batch_id=new_batch_id)

    _log_stage("start.http_returning", req_ts, batch_id=new_batch_id)
    return snap


async def cancel_import_batch(batch_id: str) -> Dict[str, Any]:
    bid = str(batch_id or "").strip()
    batch = get_batch(bid)
    if not batch:
        return build_status_snapshot("未找到要取消的批次")

    state = str(batch.get("state") or "").strip().lower()
    if state not in ("queued", "running", "paused"):
        return build_status_snapshot("当前批次不可取消")

    cancel_queued_tasks_in_batch(bid)

    _settle_batch_state_from_tasks(
        bid,
        "取消已提交：当前正在导入的文件会执行完，未开始任务将被取消",
    )

    snap = _emit_status_snapshot("取消已提交：当前正在导入的文件会执行完，未开始任务将被取消")
    return snap


async def retry_import_batch(batch_id: str) -> Dict[str, Any]:
    req_ts = time.perf_counter()
    bid = str(batch_id or "").strip()
    _log_stage("retry.request_received", req_ts, batch_id=bid)

    batch = get_batch(bid)
    if not batch:
        _log_stage("retry.batch_not_found", req_ts, batch_id=bid)
        return build_status_snapshot("未找到要重试的批次")

    state = str(batch.get("state") or "").strip().lower()
    if state not in ("failed", "cancelled", "paused"):
        _log_stage("retry.invalid_state", req_ts, batch_id=bid, state=state)
        return build_status_snapshot("当前批次不可重试")

    _log_stage("retry.batch_validated", req_ts, batch_id=bid, state=state)

    old_items = list_tasks_for_batch(bid)
    _log_stage("retry.items_loaded", req_ts, batch_id=bid, items_count=len(old_items or []))
    if not old_items:
        return build_status_snapshot("当前批次缺少可重试任务明细")

    norm_items = _normalize_items(old_items)
    _log_stage("retry.items_normalized", req_ts, batch_id=bid, normalized_items_count=len(norm_items))

    runtime = get_local_import_runtime()

    _log_stage("retry.before_require_persisted_snapshot", req_ts, batch_id=bid)
    try:
        snapshot = runtime.require_persisted_snapshot()
    except Exception:
        _log_stage("retry.persisted_snapshot_missing", req_ts, batch_id=bid)
        return build_status_snapshot("当前没有可用候选结果，请先刷新候选")

    _log_stage(
        "retry.after_require_persisted_snapshot",
        req_ts,
        batch_id=bid,
        snapshot_generated_at=snapshot.get("generated_at"),
        snapshot_items_count=len(snapshot.get("items") or []),
    )

    mark_batch_queued_for_retry(bid)
    _log_stage("retry.batch_requeued", req_ts, batch_id=bid)

    changed_tasks = reset_retryable_tasks(bid)
    _log_stage("retry.tasks_reset_done", req_ts, batch_id=bid, reset_count=len(changed_tasks or []))

    _settle_batch_state_from_tasks(
        bid,
        "批次已重新启动，正在准备导入任务",
    )

    snap = _emit_status_snapshot("批次已重新启动，正在准备导入任务")
    _log_stage("retry.first_status_emitted", req_ts, batch_id=bid)

    _schedule_drive_pipeline(
        preferred_batch_id=bid,
        preferred_items=norm_items,
        trigger="retry",
    )
    _log_stage("retry.background_pipeline_scheduled", req_ts, batch_id=bid)

    _log_stage("retry.http_returning", req_ts, batch_id=bid)
    return snap


async def drive_pipeline(
    preferred_batch_id: Optional[str] = None,
    preferred_items: Optional[List[Dict[str, Any]]] = None,
    trigger: str = "unknown",
    scheduled_at: Optional[float] = None,
) -> Dict[str, Any]:
    pipeline_ts = time.perf_counter()

    if scheduled_at is not None:
        _LOG.info(
            "[LOCAL_IMPORT][TIMING] stage=pipeline.schedule_to_runner payload=%s",
            {
                "elapsed_ms": int((pipeline_ts - scheduled_at) * 1000),
                "trigger": trigger,
                "preferred_batch_id": preferred_batch_id,
            },
        )

    runtime = get_local_import_runtime()

    _log_stage(
        "pipeline.lock_wait_begin",
        pipeline_ts,
        trigger=trigger,
        preferred_batch_id=preferred_batch_id,
    )
    await runtime.lock()
    _log_stage(
        "pipeline.lock_acquired",
        pipeline_ts,
        trigger=trigger,
        preferred_batch_id=preferred_batch_id,
    )

    try:
        snapshot = runtime.require_persisted_snapshot()
        _log_stage(
            "pipeline.persisted_snapshot_consumed",
            pipeline_ts,
            trigger=trigger,
            preferred_batch_id=preferred_batch_id,
            snapshot_generated_at=snapshot.get("generated_at"),
        )

        snap = await _advance_pipeline_if_possible(
            preferred_batch_id=preferred_batch_id,
            preferred_items=preferred_items,
            trigger=trigger,
            pipeline_start_ts=pipeline_ts,
        )

        _log_stage(
            "pipeline.advance_done",
            pipeline_ts,
            trigger=trigger,
            preferred_batch_id=preferred_batch_id,
        )
        return snap
    finally:
        runtime.unlock()
        _log_stage(
            "pipeline.lock_released",
            pipeline_ts,
            trigger=trigger,
            preferred_batch_id=preferred_batch_id,
        )
