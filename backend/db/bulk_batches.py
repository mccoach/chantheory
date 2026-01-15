# backend/db/bulk_batches.py
# ==============================
# After Hours Bulk v1.1 - 批次真相源（DB层）
#
# 职责：
#   - bulk_batches：批次快照的创建/查询/更新（进度真相源）
#   - bulk_failures：失败明细的写入与分页查询
#
# 约束：
#   - state 仅允许：'running' | 'finished'
#   - progress.version 单调递增（由业务层保证）
#   - 409/400 错误结构由路由层负责（DB层只返回数据/布尔）
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from backend.db.connection import get_conn, get_write_lock
from backend.utils.time import now_iso

_ALLOWED_STATE = {"running", "finished"}


def _row_to_batch(row) -> Dict[str, Any]:
    b: Dict[str, Any] = {
        "batch_id": row["batch_id"],
        "client_instance_id": row["client_instance_id"],
        "purpose": row["purpose"],
        "started_at": row["started_at"],
        "server_received_at": row["server_received_at"],
        "selected_symbols": row["selected_symbols"],
        "planned_total_tasks": row["planned_total_tasks"],
        "accepted_tasks": row["accepted_tasks"],
        "rejected_tasks": row["rejected_tasks"],
        "state": row["state"],
        "progress": {
            "version": row["progress_version"],
            "updated_at": row["progress_updated_at"],
            "seq": row["progress_done"],
            "done": row["progress_done"],
            "success": row["progress_success"],
            "failed": row["progress_failed"],
            "total": row["progress_total"],
        },
    }
    return b


def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM bulk_batches WHERE batch_id=? LIMIT 1;", (batch_id,))
    row = cur.fetchone()
    return _row_to_batch(row) if row else None


def get_batch_state(batch_id: str) -> Optional[str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state FROM bulk_batches WHERE batch_id=? LIMIT 1;", (batch_id,))
    row = cur.fetchone()
    return str(row[0]) if row and row[0] else None


def create_batch_if_not_exists(
    *,
    batch_id: str,
    client_instance_id: Optional[str],
    purpose: str,
    started_at: Optional[str],
    selected_symbols: Optional[int],
    planned_total_tasks: Optional[int],
    accepted_tasks: int,
    rejected_tasks: int,
) -> Tuple[str, Dict[str, Any]]:
    """
    创建批次（若不存在），并返回 (mode, batch_snapshot)

    mode:
      - 'created'   : 本次新建
      - 'existing'  : 已存在（不修改、不重复入队由路由层保证）
    """
    now = now_iso()
    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT * FROM bulk_batches WHERE batch_id=? LIMIT 1;", (batch_id,))
        row = cur.fetchone()
        if row:
            return "existing", _row_to_batch(row)

        state = "running"
        if state not in _ALLOWED_STATE:
            state = "running"

        sql = """
        INSERT INTO bulk_batches (
          batch_id, client_instance_id, purpose,
          started_at, server_received_at,
          selected_symbols, planned_total_tasks,
          accepted_tasks, rejected_tasks,
          state,
          progress_version, progress_updated_at,
          progress_done, progress_success, progress_failed, progress_total
        ) VALUES (
          :batch_id, :client_instance_id, :purpose,
          :started_at, :server_received_at,
          :selected_symbols, :planned_total_tasks,
          :accepted_tasks, :rejected_tasks,
          :state,
          :progress_version, :progress_updated_at,
          :progress_done, :progress_success, :progress_failed, :progress_total
        );
        """

        cur.execute(
            sql,
            {
                "batch_id": batch_id,
                "client_instance_id": client_instance_id,
                "purpose": purpose,
                "started_at": started_at,
                "server_received_at": now,
                "selected_symbols": selected_symbols,
                "planned_total_tasks": planned_total_tasks,
                "accepted_tasks": int(accepted_tasks),
                "rejected_tasks": int(rejected_tasks),
                "state": state,
                # v1.1：创建时 version=1，done=0
                "progress_version": 1,
                "progress_updated_at": now,
                "progress_done": 0,
                "progress_success": 0,
                "progress_failed": 0,
                # total 只统计 accepted_tasks（闭环口径）
                "progress_total": int(accepted_tasks),
            },
        )

        conn.commit()

        cur.execute("SELECT * FROM bulk_batches WHERE batch_id=? LIMIT 1;", (batch_id,))
        row2 = cur.fetchone()
        return "created", _row_to_batch(row2)


def get_latest_batch(
    *,
    purpose: Optional[str] = None,
    state: Optional[str] = None,
    client_instance_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    latest 查找：按 server_received_at 倒序取 1 条
    """
    conn = get_conn()
    cur = conn.cursor()

    where = []
    params: List[Any] = []

    if purpose:
        where.append("purpose=?")
        params.append(purpose)

    if state:
        where.append("state=?")
        params.append(state)

    if client_instance_id:
        where.append("client_instance_id=?")
        params.append(client_instance_id)

    where_sql = " AND ".join(where) if where else "1=1"

    cur.execute(
        f"""
        SELECT * FROM bulk_batches
        WHERE {where_sql}
        ORDER BY server_received_at DESC
        LIMIT 1;
        """,
        params,
    )
    row = cur.fetchone()
    return _row_to_batch(row) if row else None


def update_progress_on_task_done(
    *,
    batch_id: str,
    overall_status: str,
) -> Optional[Dict[str, Any]]:
    """
    在某个 batch 内，一个 Task 完成时更新进度并返回最新快照。

    规则（v1.1 写死）：
      - total = accepted_tasks（建批次时已固化为 progress_total）
      - success += 1 当 overall_status == 'success'
      - failed  += 1 当 overall_status in ('failed','partial_fail')（partial_fail 计失败）
      - done = success + failed
      - seq = done
      - version 每次发生变化必须 +1
      - 当 done >= total -> state='finished'
    """
    st = str(overall_status or "").strip().lower()
    is_succ = st == "success"
    is_fail = st in ("failed", "partial_fail")

    if not (is_succ or is_fail):
        # 未知状态不参与统计（避免污染闭环）
        return get_batch(batch_id)

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        # 读当前行（确保幂等与闭环）
        cur.execute("SELECT * FROM bulk_batches WHERE batch_id=? LIMIT 1;", (batch_id,))
        row = cur.fetchone()
        if not row:
            return None

        succ = int(row["progress_success"] or 0)
        fail = int(row["progress_failed"] or 0)
        total = int(row["progress_total"] or 0)
        ver = int(row["progress_version"] or 1)

        if is_succ:
            succ += 1
        elif is_fail:
            fail += 1

        done = succ + fail

        # 状态闭环：done >= total => finished
        state = "finished" if (total > 0 and done >= total) else "running"

        # version 单调递增
        ver = ver + 1

        cur.execute(
            """
            UPDATE bulk_batches
            SET
              state=?,
              progress_version=?,
              progress_updated_at=?,
              progress_done=?,
              progress_success=?,
              progress_failed=?
            WHERE batch_id=?;
            """,
            (state, ver, now, done, succ, fail, batch_id),
        )

        conn.commit()

        cur.execute("SELECT * FROM bulk_batches WHERE batch_id=? LIMIT 1;", (batch_id,))
        row2 = cur.fetchone()
        return _row_to_batch(row2) if row2 else None


def upsert_failure_once(
    *,
    batch_id: str,
    task_id: str,
    task_type: Optional[str],
    symbol: Optional[str],
    freq: Optional[str],
    adjust: Optional[str],
    overall_status: str,
    error_code: Optional[str],
    error_message: Optional[str],
    timestamp: str,
) -> None:
    """
    失败明细：按 (batch_id, task_id) 唯一，重复写入应幂等覆盖/忽略。
    """
    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bulk_failures (
              batch_id,
              task_id, task_type, symbol, freq, adjust,
              overall_status,
              error_code, error_message,
              timestamp
            ) VALUES (
              :batch_id,
              :task_id, :task_type, :symbol, :freq, :adjust,
              :overall_status,
              :error_code, :error_message,
              :timestamp
            )
            ON CONFLICT(batch_id, task_id) DO UPDATE SET
              task_type=excluded.task_type,
              symbol=excluded.symbol,
              freq=excluded.freq,
              adjust=excluded.adjust,
              overall_status=excluded.overall_status,
              error_code=excluded.error_code,
              error_message=excluded.error_message,
              timestamp=excluded.timestamp;
            """,
            {
                "batch_id": batch_id,
                "task_id": task_id,
                "task_type": task_type,
                "symbol": symbol,
                "freq": freq,
                "adjust": adjust,
                "overall_status": overall_status,
                "error_code": error_code,
                "error_message": error_message,
                "timestamp": timestamp,
            },
        )
        conn.commit()


def list_failures(
    *,
    batch_id: str,
    offset: int = 0,
    limit: int = 200,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    分页查询失败明细，返回 (total_failed, items)
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM bulk_failures WHERE batch_id=?;",
        (batch_id,),
    )
    total = int(cur.fetchone()[0] or 0)

    cur.execute(
        """
        SELECT
          task_id,
          task_type,
          symbol,
          freq,
          adjust,
          overall_status,
          error_code,
          error_message,
          timestamp
        FROM bulk_failures
        WHERE batch_id=?
        ORDER BY id ASC
        LIMIT ? OFFSET ?;
        """,
        (batch_id, int(limit), int(offset)),
    )
    rows = cur.fetchall()

    items = [dict(r) for r in rows]
    return total, items
