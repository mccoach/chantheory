# backend/services/bulk_scheduler.py
# ==============================
# After Hours Bulk - 单 active + FIFO queued 调度器（inflight 闸门版）
#
# 关键变更：
#   - 不再把一个批次的 queued tasks 全量入队
#   - 改为 inflight 闸门：保证 bulk_tasks.status='running' <= settings.bulk_max_inflight_tasks
#   - 提供 refill_inflight：任务终结后补发 queued tasks，保持细水长流
# ==============================

from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any

from backend.settings import settings
from backend.services.priority_queue import get_priority_queue
from backend.services.task_model import create_task
from backend.db.bulk_batches import (
    get_batch_snapshot_for_client,
    get_active_batch_for_client,
    list_queued_tasks_for_batch,
    mark_task_running,
    tick_pick_next_queued,
    count_tasks_by_status,
    get_batch_state_for_client,
)
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("bulk_scheduler")


async def enqueue_batch(
    *,
    batch_id: str,
    client_instance_id: str,
    trace_id: Optional[str],
) -> int:
    """
    限额入队：将 queued tasks 入队，并标记为 running（不会超过 inflight 上限）。

    Returns:
        int: 实际入队的任务数
    """
    bid = str(batch_id or "").strip()
    cid = str(client_instance_id or "").strip()
    if not bid or not cid:
        return 0

    # 若批次非 running，则不补发（尤其 stopping/paused）
    st = await asyncio.to_thread(get_batch_state_for_client, batch_id=bid, client_instance_id=cid)
    if st != "running":
        return 0

    try:
        max_inflight = max(1, int(getattr(settings, "bulk_max_inflight_tasks", 8)))
    except Exception:
        max_inflight = 8

    running_cnt = await asyncio.to_thread(count_tasks_by_status, batch_id=bid, status="running")
    quota = max(0, int(max_inflight) - int(running_cnt))
    if quota <= 0:
        return 0

    queue = get_priority_queue()

    # 只读取 quota 条 queued tasks
    tasks = await asyncio.to_thread(
        list_queued_tasks_for_batch,
        batch_id=bid,
        limit=quota,
    )
    if not tasks:
        return 0

    enqueued = 0
    for t in tasks:
        ckey = t["client_task_key"]

        ok = await asyncio.to_thread(
            mark_task_running,
            batch_id=bid,
            client_task_key=ckey,
            last_task_id=None,
        )
        if not ok:
            continue

        task = create_task(
            type=t["type"],
            scope=t["scope"],
            symbol=t.get("symbol"),
            freq=t.get("freq"),
            adjust=t.get("adjust") or "none",
            trace_id=trace_id,
            params=t.get("params") or {},
            source="api/ensure-data/bulk",
            priority=None,
        )

        task.metadata["batch_id"] = bid
        task.metadata["client_instance_id"] = cid
        task.metadata["batch_purpose"] = "after_hours"
        task.metadata["client_task_key"] = ckey

        await queue.enqueue(task)
        enqueued += 1

        if enqueued % 200 == 0:
            await asyncio.sleep(0)

    log_event(
        logger=_LOG,
        service="bulk_scheduler",
        level="INFO",
        file=__file__,
        func="enqueue_batch",
        line=0,
        trace_id=trace_id,
        event="bulk.enqueue.limited",
        message="bulk inflight enqueue done",
        extra={
            "batch_id": bid,
            "client_instance_id": cid,
            "enqueued": enqueued,
            "max_inflight": max_inflight,
            "running_before": running_cnt,
        },
    )

    return enqueued


async def refill_inflight(
    *,
    batch_id: str,
    client_instance_id: str,
    trace_id: Optional[str],
) -> int:
    """
    inflight 补发入口：用于 task.finished hook 在任务终结后调用。
    """
    return await enqueue_batch(batch_id=batch_id, client_instance_id=client_instance_id, trace_id=trace_id)


async def tick(
    *,
    client_instance_id: str,
    trace_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    调度 tick：
      - 若当前 client_instance_id 下存在 active batch（running/paused/stopping）→ 不做事
      - 否则：取 FIFO 最早 queued 批次，置为 running，并按 inflight 上限入队一小批任务

    Returns:
        Optional[batch_snapshot]
    """
    cid = str(client_instance_id or "").strip()
    if not cid:
        return None

    active = await asyncio.to_thread(
        get_active_batch_for_client,
        client_instance_id=cid,
        purpose="after_hours",
    )
    if active:
        return None

    picked = await asyncio.to_thread(
        tick_pick_next_queued,
        client_instance_id=cid,
        purpose="after_hours",
    )
    if not picked:
        return None

    bid = picked["batch_id"]

    await enqueue_batch(
        batch_id=bid,
        client_instance_id=cid,
        trace_id=trace_id,
    )

    snap = await asyncio.to_thread(
        get_batch_snapshot_for_client,
        batch_id=bid,
        client_instance_id=cid,
    )
    return snap
