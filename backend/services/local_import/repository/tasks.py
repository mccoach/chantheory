# backend/services/local_import/repository/tasks.py
# ==============================
# 盘后数据导入 import - 任务表持久化访问
#
# 最终模型：
#   - queued batch 不提前展开为 tasks
#   - 只有 running/paused/最后有效终态批次允许在 tasks 表中存在任务
#   - tasks 表始终是执行态唯一真相源
#
# 当前重构重点：
#   - 所有进度一律从 tasks 聚合得到
#   - batch 不再持有 progress_* 解释权
#
# 本轮改动（任务追溯字段）：
#   - 删除 updated_at
#   - 删除 error_code / error_message
#   - 收敛为：
#       * signal_code
#       * signal_message
#   - 新增：
#       * appended_rows
#       * source_file_path
#       * started_at
#       * finished_at
# ==============================

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple

from backend.db.connection import get_conn, get_write_lock
from backend.utils.time import now_iso

from .common import _safe_task_state, _joined_row_to_task_dict


def create_tasks_for_batch(batch_id: str, items: List[Dict[str, Any]]) -> int:
    """
    为某个 batch 显式创建 tasks。
    只应在 batch 正式进入 running 时调用。
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return 0
    if not items:
        return 0

    payload = []
    for item in items:
        market = str(item.get("market") or "").strip().upper()
        symbol = str(item.get("symbol") or "").strip()
        freq = str(item.get("freq") or "").strip()
        if market not in ("SH", "SZ", "BJ") or not symbol or not freq:
            continue
        payload.append((
            bid,
            market,
            symbol,
            freq,
            "queued",
            0,
            None,
            None,
            None,
            None,
            None,
            None,
        ))

    if not payload:
        return 0

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT OR IGNORE INTO local_import_tasks (
                batch_id,
                market,
                symbol,
                freq,
                state,
                attempts,
                signal_code,
                signal_message,
                appended_rows,
                source_file_path,
                started_at,
                finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            payload,
        )
        conn.commit()
        return int(cur.rowcount or 0)


def delete_tasks_for_batch(batch_id: str) -> int:
    bid = str(batch_id or "").strip()
    if not bid:
        return 0

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM local_import_tasks WHERE batch_id=?;", (bid,))
        affected = int(cur.rowcount or 0)
        conn.commit()
    return affected


def delete_tasks_for_batches(batch_ids: List[str]) -> int:
    ids = [str(x).strip() for x in (batch_ids or []) if str(x).strip()]
    if not ids:
        return 0

    total = 0
    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        for bid in ids:
            cur.execute("DELETE FROM local_import_tasks WHERE batch_id=?;", (bid,))
            total += int(cur.rowcount or 0)
        conn.commit()
    return total


def delete_tasks_except_batch_ids(keep_batch_ids: List[str]) -> int:
    keep_ids = [str(x).strip() for x in (keep_batch_ids or []) if str(x).strip()]

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        if not keep_ids:
            cur.execute("DELETE FROM local_import_tasks;")
            affected = int(cur.rowcount or 0)
            conn.commit()
            return affected

        placeholders = ",".join(["?"] * len(keep_ids))
        sql = f"DELETE FROM local_import_tasks WHERE batch_id NOT IN ({placeholders});"
        cur.execute(sql, keep_ids)
        affected = int(cur.rowcount or 0)
        conn.commit()
        return affected


def delete_orphan_tasks() -> int:
    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM local_import_tasks
            WHERE batch_id NOT IN (
                SELECT batch_id FROM local_import_batches
            );
            """
        )
        affected = int(cur.rowcount or 0)
        conn.commit()
    return affected


def list_tasks_for_batch(batch_id: str) -> List[Dict[str, Any]]:
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
            t.signal_code,
            t.signal_message,
            t.appended_rows,
            t.source_file_path,
            t.started_at,
            t.finished_at,
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


def get_task(batch_id: str, market: str, symbol: str, freq: str) -> Optional[Dict[str, Any]]:
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
            t.signal_code,
            t.signal_message,
            t.appended_rows,
            t.source_file_path,
            t.started_at,
            t.finished_at,
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
                signal_code=NULL,
                signal_message=NULL,
                appended_rows=NULL,
                source_file_path=NULL,
                started_at=?,
                finished_at=NULL
            WHERE batch_id=? AND market=? AND symbol=? AND freq=? AND state='queued';
            """,
            (now, bid, m, s, f),
        )
        conn.commit()

    return get_task(batch_id=bid, market=m, symbol=s, freq=f)


def mark_task_terminal(
    batch_id: str,
    market: str,
    symbol: str,
    freq: str,
    terminal_state: str,
    signal_code: Optional[str],
    signal_message: Optional[str],
    appended_rows: Optional[int],
    source_file_path: Optional[str],
) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()
    f = str(freq or "").strip()
    st = _safe_task_state(terminal_state)

    if st not in ("success", "failed"):
        raise ValueError(f"invalid terminal task state: {terminal_state}")

    finished_at = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE local_import_tasks
            SET state=?,
                signal_code=?,
                signal_message=?,
                appended_rows=?,
                source_file_path=?,
                finished_at=?
            WHERE batch_id=? AND market=? AND symbol=? AND freq=? AND state='running';
            """,
            (
                st,
                signal_code,
                signal_message,
                appended_rows,
                source_file_path,
                finished_at,
                bid,
                m,
                s,
                f,
            ),
        )
        conn.commit()

    return get_task(batch_id=bid, market=m, symbol=s, freq=f)


def cancel_queued_tasks_in_batch(batch_id: str) -> List[Dict[str, Any]]:
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
            t.signal_code,
            t.signal_message,
            t.appended_rows,
            t.source_file_path,
            t.started_at,
            t.finished_at,
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

    out: List[Dict[str, Any]] = []
    for row in before_rows:
        item = _joined_row_to_task_dict(row)
        item["state"] = "cancelled"
        item["signal_code"] = None
        item["signal_message"] = None
        item["appended_rows"] = None
        item["source_file_path"] = None
        item["started_at"] = None
        item["finished_at"] = None
        out.append(item)

    with get_write_lock():
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute(
            """
            UPDATE local_import_tasks
            SET state='cancelled',
                signal_code=NULL,
                signal_message=NULL,
                appended_rows=NULL,
                source_file_path=NULL,
                started_at=NULL,
                finished_at=NULL
            WHERE batch_id=? AND state='queued';
            """,
            (bid,),
        )
        conn2.commit()

    return out


def reset_retryable_tasks(batch_id: str) -> List[Dict[str, Any]]:
    """
    retry 语义：
      - success 不动
      - failed -> queued
      - cancelled -> queued
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
            t.signal_code,
            t.signal_message,
            t.appended_rows,
            t.source_file_path,
            t.started_at,
            t.finished_at,
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

    out: List[Dict[str, Any]] = []
    for row in before_rows:
        item = _joined_row_to_task_dict(row)
        item["state"] = "queued"
        item["signal_code"] = None
        item["signal_message"] = None
        item["appended_rows"] = None
        item["source_file_path"] = None
        item["started_at"] = None
        item["finished_at"] = None
        out.append(item)

    with get_write_lock():
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute(
            """
            UPDATE local_import_tasks
            SET state='queued',
                signal_code=NULL,
                signal_message=NULL,
                appended_rows=NULL,
                source_file_path=NULL,
                started_at=NULL,
                finished_at=NULL
            WHERE batch_id=? AND state IN ('failed', 'cancelled');
            """,
            (bid,),
        )
        conn2.commit()

    return out


def mark_interrupted_running_tasks_failed(batch_id: str) -> List[Dict[str, Any]]:
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
            t.signal_code,
            t.signal_message,
            t.appended_rows,
            t.source_file_path,
            t.started_at,
            t.finished_at,
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

    finished_at = now_iso()

    out: List[Dict[str, Any]] = []
    for row in before_rows:
        item = _joined_row_to_task_dict(row)
        item["state"] = "failed"
        item["signal_code"] = "INTERRUPTED"
        item["signal_message"] = "服务异常中断，任务未正常完成，请检查后重试"
        item["appended_rows"] = None
        item["source_file_path"] = None
        item["finished_at"] = finished_at
        out.append(item)

    with get_write_lock():
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute(
            """
            UPDATE local_import_tasks
            SET state='failed',
                signal_code='INTERRUPTED',
                signal_message='服务异常中断，任务未正常完成，请检查后重试',
                appended_rows=NULL,
                source_file_path=NULL,
                finished_at=?
            WHERE batch_id=? AND state='running';
            """,
            (finished_at, bid),
        )
        conn2.commit()

    return out


def get_batch_counts(batch_id: str) -> Tuple[int, int, int, int, int]:
    """
    从 tasks 真相源聚合任务状态计数。
    返回：
      queued, running, success, failed, cancelled
    """
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
