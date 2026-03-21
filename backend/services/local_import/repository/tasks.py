# backend/services/local_import/repository/tasks.py
# ==============================
# 盘后数据导入 import - 任务表持久化访问
# ==============================

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple

from backend.db.connection import get_conn, get_write_lock
from backend.utils.time import now_iso

from .common import _safe_task_state, _joined_row_to_task_dict


def list_tasks_for_batch(batch_id: str) -> List[Dict[str, Any]]:
    """
    任务列表一次性 JOIN symbol_index，避免 N+1 查询。
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return []

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            t.batch_id,
            t.market,
            t.symbol,
            t.freq,
            t.state,
            t.attempts,
            t.error_code,
            t.error_message,
            t.updated_at,
            s.name AS name,
            s.class AS class,
            s.type AS type
        FROM local_import_tasks t
        LEFT JOIN symbol_index s
          ON t.symbol = s.symbol AND t.market = s.market
        WHERE t.batch_id=?
        ORDER BY t.market ASC, t.symbol ASC, t.freq ASC;
        """,
        (bid,),
    )
    rows = cur.fetchall()
    return [_joined_row_to_task_dict(r) for r in rows]


def get_next_queued_task(batch_id: str) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    if not bid:
        return None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_tasks
        WHERE batch_id=? AND state='queued'
        ORDER BY market ASC, symbol ASC, freq ASC
        LIMIT 1;
        """,
        (bid,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_running_task(batch_id: str) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    if not bid:
        return None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM local_import_tasks
        WHERE batch_id=? AND state='running'
        LIMIT 1;
        """,
        (bid,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def mark_task_running(batch_id: str, market: str, symbol: str, freq: str) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()
    f = str(freq or "").strip()
    if not bid or not m or not s or not f:
        return None

    now = now_iso()
    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE local_import_tasks
            SET state='running',
                attempts=attempts+1,
                error_code=NULL,
                error_message=NULL,
                updated_at=?
            WHERE batch_id=? AND market=? AND symbol=? AND freq=? AND state='queued';
            """,
            (now, bid, m, s, f),
        )
        conn.commit()

    return get_task(batch_id=bid, market=m, symbol=s, freq=f)


def get_task(batch_id: str, market: str, symbol: str, freq: str) -> Optional[Dict[str, Any]]:
    """
    单任务读取同样直接 JOIN symbol_index，避免重复查库。
    """
    bid = str(batch_id or "").strip()
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()
    f = str(freq or "").strip()
    if not bid or not m or not s or not f:
        return None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            t.batch_id,
            t.market,
            t.symbol,
            t.freq,
            t.state,
            t.attempts,
            t.error_code,
            t.error_message,
            t.updated_at,
            si.name AS name,
            si.class AS class,
            si.type AS type
        FROM local_import_tasks t
        LEFT JOIN symbol_index si
          ON t.symbol = si.symbol AND t.market = si.market
        WHERE t.batch_id=? AND t.market=? AND t.symbol=? AND t.freq=?
        LIMIT 1;
        """,
        (bid, m, s, f),
    )
    row = cur.fetchone()
    return _joined_row_to_task_dict(row) if row else None


def mark_task_terminal(
    batch_id: str,
    market: str,
    symbol: str,
    freq: str,
    terminal_state: str,
    error_code: Optional[str],
    error_message: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    允许：
      - running -> success
      - running -> failed
    """
    bid = str(batch_id or "").strip()
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()
    f = str(freq or "").strip()
    st = _safe_task_state(terminal_state)

    if st not in ("success", "failed"):
        raise ValueError(f"invalid terminal task state: {terminal_state}")

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE local_import_tasks
            SET state=?,
                error_code=?,
                error_message=?,
                updated_at=?
            WHERE batch_id=? AND market=? AND symbol=? AND freq=? AND state='running';
            """,
            (st, error_code, error_message, now, bid, m, s, f),
        )
        conn.commit()

    return get_task(batch_id=bid, market=m, symbol=s, freq=f)


def cancel_queued_tasks_in_batch(batch_id: str) -> List[Dict[str, Any]]:
    """
    取消批次中所有 queued 任务，并返回真正发生 queued->cancelled 的任务列表，
    供 orchestrator 逐条发 task_changed。
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return []

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            t.batch_id,
            t.market,
            t.symbol,
            t.freq,
            t.state,
            t.attempts,
            t.error_code,
            t.error_message,
            t.updated_at,
            s.name AS name,
            s.class AS class,
            s.type AS type
        FROM local_import_tasks t
        LEFT JOIN symbol_index s
          ON t.symbol = s.symbol AND t.market = s.market
        WHERE t.batch_id=? AND t.state='queued'
        ORDER BY t.market ASC, t.symbol ASC, t.freq ASC;
        """,
        (bid,),
    )
    before_rows = cur.fetchall()
    if not before_rows:
        return []

    now = now_iso()

    with get_write_lock():
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute(
            """
            UPDATE local_import_tasks
            SET state='cancelled',
                updated_at=?
            WHERE batch_id=? AND state='queued';
            """,
            (now, bid),
        )
        conn2.commit()

    out: List[Dict[str, Any]] = []
    for row in before_rows:
        item = _joined_row_to_task_dict(row)
        item["state"] = "cancelled"
        item["updated_at"] = now
        out.append(item)

    return out


def reset_retryable_tasks(batch_id: str) -> List[Dict[str, Any]]:
    """
    retry 语义：
      - success 不动
      - failed -> queued
      - cancelled -> queued

    返回真正发生状态重置的任务列表，供 orchestrator 逐条发 task_changed。
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return []

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            t.batch_id,
            t.market,
            t.symbol,
            t.freq,
            t.state,
            t.attempts,
            t.error_code,
            t.error_message,
            t.updated_at,
            s.name AS name,
            s.class AS class,
            s.type AS type
        FROM local_import_tasks t
        LEFT JOIN symbol_index s
          ON t.symbol = s.symbol AND t.market = s.market
        WHERE t.batch_id=? AND t.state IN ('failed', 'cancelled')
        ORDER BY t.market ASC, t.symbol ASC, t.freq ASC;
        """,
        (bid,),
    )
    before_rows = cur.fetchall()
    if not before_rows:
        return []

    now = now_iso()
    with get_write_lock():
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute(
            """
            UPDATE local_import_tasks
            SET state='queued',
                error_code=NULL,
                error_message=NULL,
                updated_at=?
            WHERE batch_id=? AND state IN ('failed', 'cancelled');
            """,
            (now, bid),
        )
        conn2.commit()

    out: List[Dict[str, Any]] = []
    for row in before_rows:
        item = _joined_row_to_task_dict(row)
        item["state"] = "queued"
        item["error_code"] = None
        item["error_message"] = None
        item["updated_at"] = now
        out.append(item)

    return out


def mark_interrupted_running_tasks_failed(batch_id: str) -> List[Dict[str, Any]]:
    """
    启动恢复时使用：
      - 将该批次内仍处于 running 的任务纠偏为 failed(INTERRUPTED)
      - 返回真正被纠偏的任务列表
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return []

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            t.batch_id,
            t.market,
            t.symbol,
            t.freq,
            t.state,
            t.attempts,
            t.error_code,
            t.error_message,
            t.updated_at,
            s.name AS name,
            s.class AS class,
            s.type AS type
        FROM local_import_tasks t
        LEFT JOIN symbol_index s
          ON t.symbol = s.symbol AND t.market = s.market
        WHERE t.batch_id=? AND t.state='running'
        ORDER BY t.market ASC, t.symbol ASC, t.freq ASC;
        """,
        (bid,),
    )
    before_rows = cur.fetchall()
    if not before_rows:
        return []

    now = now_iso()
    with get_write_lock():
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute(
            """
            UPDATE local_import_tasks
            SET state='failed',
                error_code='INTERRUPTED',
                error_message='服务异常中断，任务未正常完成，请检查后重试',
                updated_at=?
            WHERE batch_id=? AND state='running';
            """,
            (now, bid),
        )
        conn2.commit()

    out: List[Dict[str, Any]] = []
    for row in before_rows:
        item = _joined_row_to_task_dict(row)
        item["state"] = "failed"
        item["error_code"] = "INTERRUPTED"
        item["error_message"] = "服务异常中断，任务未正常完成，请检查后重试"
        item["updated_at"] = now
        out.append(item)

    return out


def get_batch_counts(batch_id: str) -> Tuple[int, int, int, int, int]:
    bid = str(batch_id or "").strip()
    if not bid:
        return 0, 0, 0, 0, 0

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT state, COUNT(*) AS n
        FROM local_import_tasks
        WHERE batch_id=?
        GROUP BY state;
        """,
        (bid,),
    )
    rows = cur.fetchall()

    counts = {"queued": 0, "running": 0, "success": 0, "failed": 0, "cancelled": 0}
    for row in rows:
        st = _safe_task_state(row["state"])
        counts[st] = int(row["n"] or 0)

    return (
        counts["queued"],
        counts["running"],
        counts["success"],
        counts["failed"],
        counts["cancelled"],
    )
