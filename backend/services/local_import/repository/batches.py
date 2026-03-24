# backend/services/local_import/repository/batches.py
# ==============================
# 盘后数据导入 import - 批次表持久化访问
#
# 重构原则（按最终模型）：
#   - batch 是调度层对象
#   - task  是运行层对象
#   - queued batch 不提前展开为 tasks
#   - 只有 running/paused 批次允许在 tasks 表中存在任务
#
# 状态单向规则：
#   - queued  只能单向进入 running，不允许回退
#   - running 只允许进入 success/failed/cancelled/paused
#   - retry 才允许：
#       failed/cancelled/paused -> queued
#
# 展示规则：
#   1) running
#   2) 最后有效终态（paused/success/failed/cancelled）
#   3) 最后一个 queued
#
# 说明：
#   - 本文件只负责批次持久化访问与批次状态机收敛
#   - 不负责调度推进
# ==============================

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.db.connection import get_conn, get_write_lock
from backend.utils.time import now_iso

from .common import _safe_batch_state, _row_to_batch_dict
from .tasks import get_batch_counts


def generate_batch_id() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"IMPORT_{ts}_{suffix}"


def create_batch(
    *,
    selection_signature: str,
    item_count: int,
) -> Dict[str, Any]:
    """
    只创建 batch，不提前创建 tasks。
    """
    batch_id = generate_batch_id()
    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO local_import_batches (
                batch_id,
                state,
                created_at,
                started_at,
                finished_at,
                progress_total,
                progress_done,
                progress_success,
                progress_failed,
                progress_cancelled,
                retryable,
                cancelable,
                ui_message,
                selection_signature
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                batch_id,
                "queued",
                now,
                None,
                None,
                int(item_count or 0),
                0,
                0,
                0,
                0,
                0,
                1,
                "已创建导入批次",
                str(selection_signature or "").strip() or None,
            ),
        )
        conn.commit()

    return get_batch(batch_id)


def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    if not bid:
        return None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM local_import_batches WHERE batch_id=? LIMIT 1;",
        (bid,),
    )
    row = cur.fetchone()
    return _row_to_batch_dict(row) if row else None


def list_all_batches_ordered() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_batches
        ORDER BY created_at ASC;
        """
    )
    rows = cur.fetchall()
    return [_row_to_batch_dict(r) for r in rows]


def get_batches_by_state(state: str) -> List[Dict[str, Any]]:
    st = _safe_batch_state(state)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_batches
        WHERE state=?
        ORDER BY created_at ASC;
        """,
        (st,),
    )
    rows = cur.fetchall()
    return [_row_to_batch_dict(r) for r in rows]


def get_current_running_batch() -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_batches
        WHERE state='running'
        ORDER BY created_at DESC
        LIMIT 1;
        """
    )
    row = cur.fetchone()
    return _row_to_batch_dict(row) if row else None


def get_latest_queued_batch() -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_batches
        WHERE state='queued'
        ORDER BY created_at DESC
        LIMIT 1;
        """
    )
    row = cur.fetchone()
    return _row_to_batch_dict(row) if row else None


def get_oldest_queued_batch() -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_batches
        WHERE state='queued'
        ORDER BY created_at ASC
        LIMIT 1;
        """
    )
    row = cur.fetchone()
    return _row_to_batch_dict(row) if row else None


def get_last_effective_terminal_batch() -> Optional[Dict[str, Any]]:
    """
    有效终态不包含 queued/running，只包含：
      - paused
      - success
      - failed
      - cancelled
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_batches
        WHERE state IN ('paused', 'success', 'failed', 'cancelled')
        ORDER BY created_at DESC
        LIMIT 1;
        """
    )
    row = cur.fetchone()
    return _row_to_batch_dict(row) if row else None


def get_latest_active_batch_by_signature(selection_signature: str) -> Optional[Dict[str, Any]]:
    sig = str(selection_signature or "").strip()
    if not sig:
        return None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_batches
        WHERE selection_signature=?
          AND state IN ('queued', 'running', 'paused')
        ORDER BY created_at DESC
        LIMIT 1;
        """,
        (sig,),
    )
    row = cur.fetchone()
    return _row_to_batch_dict(row) if row else None


def get_display_batch() -> Optional[Dict[str, Any]]:
    """
    display_batch 展示规则：
      1) 当前 running
      2) 最后有效终态（paused/success/failed/cancelled）
      3) 最后一个 queued
      4) 否则 None
    """
    running = get_current_running_batch()
    if running:
        return running

    terminal = get_last_effective_terminal_batch()
    if terminal:
        return terminal

    queued = get_latest_queued_batch()
    if queued:
        return queued

    return None


def list_queued_batch_summaries() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT batch_id, state, created_at, progress_total
        FROM local_import_batches
        WHERE state='queued'
        ORDER BY created_at ASC;
        """
    )
    rows = cur.fetchall()

    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        out.append({
            "batch_id": row["batch_id"],
            "state": row["state"],
            "queue_position": idx,
            "created_at": row["created_at"],
            "item_count": int(row["progress_total"] or 0),
        })
    return out


def build_status_snapshot(ui_message: Optional[str] = None) -> Dict[str, Any]:
    display_batch = get_display_batch()
    queued_batches = list_queued_batch_summaries()

    return {
        "ok": True,
        "display_batch": display_batch,
        "queued_batches": queued_batches,
        "ui_message": ui_message if ui_message is not None else (
            display_batch.get("ui_message") if display_batch else "当前无可展示批次"
        ),
    }


def mark_batch_running(batch_id: str, ui_message: str = "正在导入本地盘后文件") -> Optional[Dict[str, Any]]:
    """
    只允许：
      queued -> running
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return None

    now = now_iso()
    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE local_import_batches
            SET state='running',
                started_at=COALESCE(started_at, ?),
                finished_at=NULL,
                retryable=0,
                cancelable=1,
                ui_message=?
            WHERE batch_id=? AND state='queued';
            """,
            (now, ui_message, bid),
        )
        conn.commit()

    return get_batch(bid)


def mark_batch_paused(batch_id: str, ui_message: str = "导入被异常中断，请检查后重试") -> Optional[Dict[str, Any]]:
    """
    只允许：
      running -> paused
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return None

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE local_import_batches
            SET state='paused',
                retryable=1,
                cancelable=0,
                ui_message=?
            WHERE batch_id=? AND state='running';
            """,
            (ui_message, bid),
        )
        conn.commit()

    return get_batch(bid)


def mark_batch_queued_for_retry(batch_id: str, ui_message: str = "已重新加入失败/已取消任务，成功任务不会重复导入") -> Optional[Dict[str, Any]]:
    """
    只允许：
      failed/cancelled/paused -> queued
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return None

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE local_import_batches
            SET state='queued',
                started_at=NULL,
                finished_at=NULL,
                retryable=0,
                cancelable=1,
                progress_done=0,
                progress_failed=0,
                progress_cancelled=0,
                ui_message=?
            WHERE batch_id=? AND state IN ('failed', 'cancelled', 'paused');
            """,
            (ui_message, bid),
        )
        conn.commit()

    return get_batch(bid)


def recompute_batch_progress_and_state(batch_id: str, ui_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    重新汇总批次进度与批次状态。

    单向规则：
      - queued 不由本函数生成（queued 只来自 create/retry）
      - started_at 非空且未终态的批次，保持 running
      - 本函数只负责：
          * running 内部进度更新
          * running -> success/failed/cancelled
      - paused 不由本函数生成，paused 只由恢复链路显式设置
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return None

    queued_count, running_count, success_count, failed_count, cancelled_count = get_batch_counts(bid)
    total = queued_count + running_count + success_count + failed_count + cancelled_count
    done = success_count + failed_count + cancelled_count

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT state, started_at
        FROM local_import_batches
        WHERE batch_id=?
        LIMIT 1;
        """,
        (bid,),
    )
    batch_row = cur.fetchone()
    if not batch_row:
        return None

    old_state = _safe_batch_state(batch_row["state"])
    started_at = batch_row["started_at"]

    # paused 只由恢复链路显式控制，不在这里自动演化
    if old_state == "paused":
        return get_batch(bid)

    # queued 只允许出现在“从未开始过”的批次；本函数不把任何 started batch 回退成 queued
    new_state = old_state
    finished_at = None
    retryable = 0
    cancelable = 0

    # 若该批次从未开始过，保持 queued（只用于 create/retry 后、尚未 mark_running 之前）
    if old_state == "queued" and not started_at:
        new_state = "queued"
        cancelable = 1
        retryable = 0
        if ui_message is None:
            ui_message = "批次正在排队等待执行"

    else:
        # 只要开始过且尚未全部终态，就必须保持 running，绝不回退 queued
        if done < total:
            new_state = "running"
            cancelable = 1
            retryable = 0
            if ui_message is None:
                ui_message = "正在导入本地盘后文件"
        else:
            # 全部终态后，按优先级收敛
            if cancelled_count > 0:
                new_state = "cancelled"
                retryable = 1
                cancelable = 0
                if ui_message is None:
                    ui_message = "导入已结束：存在已取消任务"
            elif failed_count > 0:
                new_state = "failed"
                retryable = 1
                cancelable = 0
                if ui_message is None:
                    ui_message = "导入已结束：存在失败任务"
            else:
                new_state = "success"
                retryable = 0
                cancelable = 0
                if ui_message is None:
                    ui_message = "导入完成"

            finished_at = now_iso()

    with get_write_lock():
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute(
            """
            UPDATE local_import_batches
            SET state=?,
                finished_at=?,
                progress_total=?,
                progress_done=?,
                progress_success=?,
                progress_failed=?,
                progress_cancelled=?,
                retryable=?,
                cancelable=?,
                ui_message=?
            WHERE batch_id=?;
            """,
            (
                new_state,
                finished_at if finished_at is not None else None,
                total,
                done,
                success_count,
                failed_count,
                cancelled_count,
                retryable,
                cancelable,
                ui_message,
                bid,
            ),
        )
        conn2.commit()

    return get_batch(bid)


def delete_batch(batch_id: str) -> int:
    bid = str(batch_id or "").strip()
    if not bid:
        return 0

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM local_import_batches WHERE batch_id=?;", (bid,))
        affected = int(cur.rowcount or 0)
        conn.commit()
    return affected


def delete_batches(batch_ids: List[str]) -> int:
    ids = [str(x).strip() for x in (batch_ids or []) if str(x).strip()]
    if not ids:
        return 0

    total = 0
    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        for bid in ids:
            cur.execute("DELETE FROM local_import_batches WHERE batch_id=?;", (bid,))
            total += int(cur.rowcount or 0)
        conn.commit()
    return total
