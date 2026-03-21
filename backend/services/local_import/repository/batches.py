# backend/services/local_import/repository/batches.py
# ==============================
# 盘后数据导入 import - 批次表持久化访问
#
# 语义重整：
#   - 调度规则与展示规则分离
#   - 展示规则：
#       1) running
#       2) 最早 queued
#       3) 最后有效终态（paused/success/failed/cancelled）
#   - 清理规则：
#       * 新批次真正进入 running 时，清理旧终态有效批次
#
# 本次说明补充：
#   - start_import_batch 创建新批次后，调度层会优先推进当前新建批次
#   - 本文件仍只负责批次持久化访问，不承担调度决策
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
    """
    生成本地导入批次ID。
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"IMPORT_{ts}_{suffix}"


def create_batch_with_tasks(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    创建批次及任务（方案B：内部先建 tasks）。
    """
    if not items:
        raise ValueError("items must not be empty")

    batch_id = generate_batch_id()
    now = now_iso()
    total = len(items)

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
                ui_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                batch_id,
                "queued",
                now,
                None,
                None,
                total,
                0,
                0,
                0,
                0,
                0,
                1,
                "已创建导入批次",
            ),
        )

        cur.executemany(
            """
            INSERT INTO local_import_tasks (
                batch_id,
                market,
                symbol,
                freq,
                state,
                attempts,
                error_code,
                error_message,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            [
                (
                    batch_id,
                    str(item["market"]).strip().upper(),
                    str(item["symbol"]).strip(),
                    str(item["freq"]).strip(),
                    "queued",
                    0,
                    None,
                    None,
                    now,
                )
                for item in items
            ],
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


def get_current_running_batch() -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_batches
        WHERE state='running'
        ORDER BY created_at ASC
        LIMIT 1;
        """
    )
    row = cur.fetchone()
    return _row_to_batch_dict(row) if row else None


def get_first_queued_batch() -> Optional[Dict[str, Any]]:
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
    获取最后一个有效终态批次：
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


def get_display_batch() -> Optional[Dict[str, Any]]:
    """
    display_batch 纯展示规则：
      1. 有 running → running
      2. 否则有 queued → 最早 queued
      3. 否则取最后有效终态批次
      4. 否则 None
    """
    running = get_current_running_batch()
    if running:
        return running

    queued = get_first_queued_batch()
    if queued:
        return queued

    return get_last_effective_terminal_batch()


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
        "ui_message": ui_message if ui_message is not None else (display_batch.get("ui_message") if display_batch else "当前无可展示批次"),
    }


def mark_batch_running(batch_id: str, ui_message: str = "正在导入本地盘后文件") -> Optional[Dict[str, Any]]:
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


def recompute_batch_progress_and_state(batch_id: str, ui_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    重新汇总批次进度与批次状态。

    终态优先级：
      cancelled > failed > success

    说明：
      - paused 不由这里自动生成
      - paused 只由“异常中断恢复链路”显式设置
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
        "SELECT state FROM local_import_batches WHERE batch_id=? LIMIT 1;",
        (bid,),
    )
    batch_row = cur.fetchone()
    if not batch_row:
        return None

    old_state = _safe_batch_state(batch_row["state"])

    if old_state == "paused":
        return get_batch(bid)

    new_state = old_state
    finished_at = None
    retryable = 0
    cancelable = 0

    if done < total:
        if running_count > 0:
            new_state = "running"
            cancelable = 1
            retryable = 0
            if ui_message is None:
                ui_message = "正在导入本地盘后文件"
        else:
            new_state = "queued"
            cancelable = 1
            retryable = 0
            if ui_message is None:
                ui_message = "批次正在排队等待执行"
    else:
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


def delete_batch_and_tasks(batch_id: str) -> None:
    bid = str(batch_id or "").strip()
    if not bid:
        return

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM local_import_tasks WHERE batch_id=?;", (bid,))
        cur.execute("DELETE FROM local_import_batches WHERE batch_id=?;", (bid,))
        conn.commit()


def delete_all_queued_batches_except(batch_id: str) -> List[str]:
    """
    删除所有未有效进入的 queued 批次及其任务。
    返回被删除的 batch_id 列表。
    """
    keep = str(batch_id or "").strip()

    conn = get_conn()
    cur = conn.cursor()
    if keep:
        cur.execute(
            """
            SELECT batch_id
            FROM local_import_batches
            WHERE state='queued' AND batch_id<>?
            ORDER BY created_at ASC;
            """,
            (keep,),
        )
    else:
        cur.execute(
            """
            SELECT batch_id
            FROM local_import_batches
            WHERE state='queued'
            ORDER BY created_at ASC;
            """
        )

    rows = cur.fetchall()
    ids = [str(r["batch_id"]) for r in rows]

    for bid in ids:
        delete_batch_and_tasks(bid)

    return ids


def promote_first_queued_batch_to_running() -> Optional[Dict[str, Any]]:
    queued = get_first_queued_batch()
    if not queued:
        return None
    return mark_batch_running(queued["batch_id"])


def clear_previous_terminal_batches_except(batch_id: str) -> List[str]:
    """
    当新批次真正有效进入后，清理旧终态有效批次及其任务。
    """
    keep = str(batch_id or "").strip()
    if not keep:
        return []

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT batch_id
        FROM local_import_batches
        WHERE batch_id<>?
          AND state IN ('paused', 'success', 'failed', 'cancelled');
        """,
        (keep,),
    )
    rows = cur.fetchall()
    ids = [str(r["batch_id"]) for r in rows]

    for bid in ids:
        delete_batch_and_tasks(bid)

    return ids
