# backend/services/local_import/repository/batches.py
# ==============================
# 盘后数据导入 import - 批次表持久化访问
#
# 当前模型（真相源收敛版）：
#   - batch 只负责批次元信息与调度状态
#   - task  是执行态唯一真相源
#   - progress_* 已从 batch 表结构中删除
#   - 对前端展示：
#       * display_batch = batch_meta + tasks 聚合进度视图
#
# 职责边界（修复版）：
#   - 本文件同时负责：
#       1) batch 元信息持久化访问
#       2) 基于 tasks 真相源构造 display/status 视图
#   - orchestrator 不再自行拼装前端视图
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
                retryable,
                cancelable,
                ui_message,
                selection_signature
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                batch_id,
                "queued",
                now,
                None,
                None,
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


def get_display_batch_meta() -> Optional[Dict[str, Any]]:
    """
    只返回 display_batch 对应的 batch 元信息，不拼进度。
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
        SELECT batch_id, state, created_at
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
        })
    return out


def build_display_batch_view(batch: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    统一构造给前端看的 display_batch 视图：
      batch 元信息 + tasks 聚合进度
    """
    if not batch:
        return None

    bid = str(batch.get("batch_id") or "").strip()
    queued_count, running_count, success_count, failed_count, cancelled_count = get_batch_counts(bid)

    total = queued_count + running_count + success_count + failed_count + cancelled_count
    done = success_count + failed_count + cancelled_count

    view = dict(batch)
    view["progress_total"] = total
    view["progress_done"] = done
    view["progress_success"] = success_count
    view["progress_failed"] = failed_count
    view["progress_cancelled"] = cancelled_count
    view["progress_running"] = running_count
    view["progress_queued"] = queued_count
    return view


def build_status_snapshot(ui_message: Optional[str] = None) -> Dict[str, Any]:
    """
    统一构造给前端看的 status 视图：
      - display_batch 来自 batch 元信息 + tasks 聚合
      - queued_batches 来自 batch 元信息列表
    """
    raw_display_batch = get_display_batch_meta()
    display_batch = build_display_batch_view(raw_display_batch)
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


def mark_batch_queued_for_retry(
    batch_id: str,
    ui_message: str = "已重新加入失败/已取消任务，成功任务不会重复导入",
) -> Optional[Dict[str, Any]]:
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
                ui_message=?
            WHERE batch_id=? AND state IN ('failed', 'cancelled', 'paused');
            """,
            (ui_message, bid),
        )
        conn.commit()

    return get_batch(bid)


def mark_batch_terminal_state(
    batch_id: str,
    state: str,
    ui_message: str,
) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    st = _safe_batch_state(state)
    if not bid:
        return None
    if st not in ("success", "failed", "cancelled"):
        raise ValueError(f"invalid terminal batch state: {state}")

    finished_at = now_iso()
    retryable = 1 if st in ("failed", "cancelled") else 0
    cancelable = 0

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE local_import_batches
            SET state=?,
                finished_at=?,
                retryable=?,
                cancelable=?,
                ui_message=?
            WHERE batch_id=?;
            """,
            (
                st,
                finished_at,
                retryable,
                cancelable,
                ui_message,
                bid,
            ),
        )
        conn.commit()

    return get_batch(bid)


def update_batch_ui_message(batch_id: str, ui_message: str) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    if not bid:
        return None

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE local_import_batches
            SET ui_message=?
            WHERE batch_id=?;
            """,
            (ui_message, bid),
        )
        conn.commit()

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
