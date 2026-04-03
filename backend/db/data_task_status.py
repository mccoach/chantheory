# backend/db/data_task_status.py
# ==============================
# 基础数据任务状态表操作模块
#
# 职责：
#   - 维护基础数据四大任务的稳定状态真相源
#   - 不依赖 SSE 回放
#   - 不从业务表反推状态
#
# 状态模型（对外）：
#   - idle
#   - running
#   - success
#   - failed
#
# idle 内部细分（仅后端内部保留）：
#   - never_executed
#   - has_existing_data
# ==============================

from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.db.connection import get_conn, get_write_lock

_ALLOWED_TASK_TYPES = {
    "symbol_index",
    "profile_snapshot",
    "trade_calendar",
    "factor_events_snapshot",
}

_ALLOWED_STATUSES = {
    "idle",
    "running",
    "success",
    "failed",
}

_ALLOWED_IDLE_REASONS = {
    "never_executed",
    "has_existing_data",
}


def _normalize_task_type(task_type: str) -> str:
    t = str(task_type or "").strip()
    if t not in _ALLOWED_TASK_TYPES:
        raise ValueError(f"invalid data task type: {task_type!r}")
    return t


def _normalize_status(status: str) -> str:
    s = str(status or "").strip().lower()
    if s not in _ALLOWED_STATUSES:
        raise ValueError(f"invalid data task status: {status!r}")
    return s


def _normalize_idle_reason(idle_reason: Optional[str]) -> Optional[str]:
    if idle_reason is None:
        return None
    s = str(idle_reason).strip().lower()
    if s not in _ALLOWED_IDLE_REASONS:
        raise ValueError(f"invalid idle reason: {idle_reason!r}")
    return s


def upsert_data_task_status(
    *,
    task_type: str,
    task_status: str,
    idle_reason: Optional[str] = None,
    last_success_at: Optional[str] = None,
    last_failure_at: Optional[str] = None,
    last_error_message: Optional[str] = None,
) -> int:
    t = _normalize_task_type(task_type)
    s = _normalize_status(task_status)
    r = _normalize_idle_reason(idle_reason)

    now = datetime.now().isoformat()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        sql = """
        INSERT INTO data_task_status (
            task_type,
            task_status,
            idle_reason,
            last_success_at,
            last_failure_at,
            last_error_message,
            updated_at
        )
        VALUES (
            :task_type,
            :task_status,
            :idle_reason,
            :last_success_at,
            :last_failure_at,
            :last_error_message,
            :updated_at
        )
        ON CONFLICT(task_type) DO UPDATE SET
            task_status=excluded.task_status,
            idle_reason=excluded.idle_reason,
            last_success_at=COALESCE(excluded.last_success_at, data_task_status.last_success_at),
            last_failure_at=COALESCE(excluded.last_failure_at, data_task_status.last_failure_at),
            last_error_message=excluded.last_error_message,
            updated_at=excluded.updated_at;
        """

        cur.execute(
            sql,
            {
                "task_type": t,
                "task_status": s,
                "idle_reason": r,
                "last_success_at": last_success_at,
                "last_failure_at": last_failure_at,
                "last_error_message": last_error_message,
                "updated_at": now,
            },
        )
        conn.commit()
        return int(cur.rowcount or 0)


def mark_data_task_running(task_type: str) -> int:
    return upsert_data_task_status(
        task_type=task_type,
        task_status="running",
        idle_reason=None,
        last_error_message=None,
    )


def mark_data_task_success(task_type: str) -> int:
    now = datetime.now().isoformat()
    return upsert_data_task_status(
        task_type=task_type,
        task_status="success",
        idle_reason="has_existing_data",
        last_success_at=now,
        last_error_message=None,
    )


def mark_data_task_failed(task_type: str, error_message: str) -> int:
    now = datetime.now().isoformat()
    return upsert_data_task_status(
        task_type=task_type,
        task_status="failed",
        idle_reason="has_existing_data",
        last_failure_at=now,
        last_error_message=str(error_message or "").strip(),
    )


def mark_data_task_idle(task_type: str, idle_reason: str) -> int:
    return upsert_data_task_status(
        task_type=task_type,
        task_status="idle",
        idle_reason=idle_reason,
        last_error_message=None,
    )


def select_data_task_status(task_type: str) -> Optional[Dict[str, Any]]:
    t = _normalize_task_type(task_type)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            task_type,
            task_status,
            idle_reason,
            last_success_at,
            last_failure_at,
            last_error_message,
            updated_at
        FROM data_task_status
        WHERE task_type=?
        LIMIT 1;
        """,
        (t,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def select_all_data_task_status() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            task_type,
            task_status,
            idle_reason,
            last_success_at,
            last_failure_at,
            last_error_message,
            updated_at
        FROM data_task_status
        ORDER BY task_type ASC;
        """
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]
