# backend/db/bulk_batches.py
# ==============================
# After Hours Bulk v2.2.0 - skipped 支持（真相源扩展）
# + NEW: inflight 闸门支持（running计数/批次状态查询）
# ==============================

from __future__ import annotations

import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

from backend.db.connection import get_conn, get_write_lock
from backend.utils.time import now_iso

_ALLOWED_BATCH_STATE = {
    "queued", "running", "paused", "stopping", "failed", "success", "cancelled"
}
_ALLOWED_TASK_STATUS = {"queued", "running", "success", "failed", "cancelled", "skipped"}


def _row_to_snapshot(row) -> Dict[str, Any]:
    return {
        "batch_id": row["batch_id"],
        "client_instance_id": row["client_instance_id"],
        "purpose": row["purpose"],
        "state": row["state"],
        "started_at": row["started_at"],
        "server_received_at": row["server_received_at"],
        "queue_ts": row["queue_ts"],
        "progress": {
            "version": int(row["progress_version"] or 1),
            "updated_at": row["progress_updated_at"],
            "total": int(row["progress_total"] or 0),
            "done": int(row["progress_done"] or 0),
            "success": int(row["progress_success"] or 0),
            "failed": int(row["progress_failed"] or 0),
            "cancelled": int(row["progress_cancelled"] or 0),
            "skipped": int(row["progress_skipped"] or 0),
        },
    }


def _safe_batch_state(state: str) -> str:
    s = str(state or "").strip().lower()
    return s if s in _ALLOWED_BATCH_STATE else "queued"


def _safe_task_status(status: str) -> str:
    s = str(status or "").strip().lower()
    return s if s in _ALLOWED_TASK_STATUS else "queued"


def get_batch_snapshot(batch_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM bulk_batches WHERE batch_id=? LIMIT 1;", (batch_id,))
    row = cur.fetchone()
    return _row_to_snapshot(row) if row else None


def get_batch_snapshot_for_client(batch_id: str, client_instance_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM bulk_batches WHERE batch_id=? AND client_instance_id=? LIMIT 1;",
        (batch_id, client_instance_id),
    )
    row = cur.fetchone()
    return _row_to_snapshot(row) if row else None


def get_active_batch_for_client(client_instance_id: str, purpose: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM bulk_batches
        WHERE client_instance_id=? AND purpose=?
          AND state IN ('running','paused','stopping')
        ORDER BY server_received_at DESC
        LIMIT 1;
        """,
        (client_instance_id, purpose),
    )
    row = cur.fetchone()
    return _row_to_snapshot(row) if row else None


def list_queued_batches_for_client(client_instance_id: str, purpose: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM bulk_batches
        WHERE client_instance_id=? AND purpose=? AND state='queued'
        ORDER BY queue_ts ASC;
        """,
        (client_instance_id, purpose),
    )
    rows = cur.fetchall()
    return [_row_to_snapshot(r) for r in rows]


def get_queue_position(batch_id: str, client_instance_id: str, purpose: str) -> Optional[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT state, queue_ts FROM bulk_batches WHERE batch_id=? AND client_instance_id=? AND purpose=? LIMIT 1;",
        (batch_id, client_instance_id, purpose),
    )
    row = cur.fetchone()
    if not row:
        return None
    if str(row["state"]).strip().lower() != "queued":
        return None

    queue_ts = row["queue_ts"]

    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM bulk_batches
        WHERE client_instance_id=? AND purpose=? AND state='queued' AND queue_ts <= ?;
        """,
        (client_instance_id, purpose, queue_ts),
    )
    r2 = cur.fetchone()
    n = int(r2["n"] or 0) if r2 else 0
    return n if n > 0 else 1


def _insert_bulk_tasks(batch_id: str, bulk_tasks: List[Dict[str, Any]], now: str) -> None:
    conn = get_conn()
    cur = conn.cursor()

    sql = """
    INSERT INTO bulk_tasks (
      batch_id, client_task_key,
      type, scope, symbol, freq, adjust,
      params_json,
      status, attempts,
      last_error_code, last_error_message,
      last_task_id,
      updated_at
    ) VALUES (
      :batch_id, :client_task_key,
      :type, :scope, :symbol, :freq, :adjust,
      :params_json,
      :status, :attempts,
      :last_error_code, :last_error_message,
      :last_task_id,
      :updated_at
    );
    """

    prepared = []
    seen = set()
    for t in bulk_tasks or []:
        ckey = str(t.get("client_task_key") or "").strip()
        if not ckey:
            raise ValueError("client_task_key is required")
        if ckey in seen:
            raise ValueError(f"duplicate client_task_key within batch: {ckey}")
        seen.add(ckey)

        params_obj = t.get("params") if isinstance(t.get("params"), dict) else {}
        prepared.append({
            "batch_id": batch_id,
            "client_task_key": ckey,
            "type": str(t.get("type") or "").strip(),
            "scope": str(t.get("scope") or "").strip(),
            "symbol": (str(t.get("symbol")).strip() if t.get("symbol") is not None else None),
            "freq": (str(t.get("freq")).strip() if t.get("freq") is not None else None),
            "adjust": str(t.get("adjust") or "none").strip().lower(),
            "params_json": json.dumps(params_obj, ensure_ascii=False),
            "status": "queued",
            "attempts": 0,
            "last_error_code": None,
            "last_error_message": None,
            "last_task_id": None,
            "updated_at": now,
        })

    cur.executemany(sql, prepared)


def start_batch_idempotent(
    *,
    purpose: str,
    batch: Dict[str, Any],
    submit_policy: Dict[str, Any],
    bulk_tasks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    bid = str(batch.get("batch_id") or "").strip()
    cid = str(batch.get("client_instance_id") or "").strip()
    pur = str(purpose or "").strip()

    if not bid or not cid or pur != "after_hours":
        raise ValueError("invalid batch fields")

    when_active_exists = str((submit_policy or {}).get("when_active_exists") or "").strip().lower()
    if when_active_exists not in ("replace", "enqueue", "abort"):
        when_active_exists = "enqueue"

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT * FROM bulk_batches WHERE batch_id=? LIMIT 1;", (bid,))
        row0 = cur.fetchone()
        if row0:
            snap = _row_to_snapshot(row0)
            active = get_active_batch_for_client(cid, pur)
            qp = get_queue_position(bid, cid, pur) if snap.get("state") == "queued" else None
            return {
                "mode": "existing",
                "batch": snap,
                "active_batch": active,
                "queue_position": qp,
                "need_enqueue": snap.get("state") == "running",
            }

        cur.execute(
            """
            SELECT * FROM bulk_batches
            WHERE client_instance_id=? AND purpose=?
              AND state IN ('running','paused','stopping')
            ORDER BY server_received_at DESC
            LIMIT 1;
            """,
            (cid, pur),
        )
        active_row = cur.fetchone()
        active_snap = _row_to_snapshot(active_row) if active_row else None

        if active_row and when_active_exists == "abort":
            return {
                "mode": "aborted",
                "batch": None,
                "active_batch": active_snap,
                "queue_position": None,
                "need_enqueue": False,
            }

        if active_row and when_active_exists == "replace":
            _set_batch_state_locked(
                cur=cur,
                batch_id=str(active_row["batch_id"]),
                new_state="stopping",
                now=now,
                bump_version=True,
            )
            active_snap = get_batch_snapshot(str(active_row["batch_id"]))

        new_state = "queued" if active_row else "running"

        server_received_at = now
        queue_ts = server_received_at

        started_at = batch.get("started_at")
        selected_symbols = batch.get("selected_symbols")
        planned_total_tasks = batch.get("planned_total_tasks")

        accepted = len(bulk_tasks or [])
        rejected = 0

        cur.execute(
            """
            INSERT INTO bulk_batches (
              batch_id, client_instance_id, purpose,
              started_at, server_received_at,
              queue_ts,
              selected_symbols, planned_total_tasks,
              accepted_tasks, rejected_tasks,
              state,
              progress_version, progress_updated_at,
              progress_done, progress_success, progress_failed, progress_cancelled, progress_skipped, progress_total
            ) VALUES (
              :batch_id, :client_instance_id, :purpose,
              :started_at, :server_received_at,
              :queue_ts,
              :selected_symbols, :planned_total_tasks,
              :accepted_tasks, :rejected_tasks,
              :state,
              :progress_version, :progress_updated_at,
              :progress_done, :progress_success, :progress_failed, :progress_cancelled, :progress_skipped, :progress_total
            );
            """,
            {
                "batch_id": bid,
                "client_instance_id": cid,
                "purpose": pur,
                "started_at": started_at,
                "server_received_at": server_received_at,
                "queue_ts": queue_ts,
                "selected_symbols": selected_symbols,
                "planned_total_tasks": planned_total_tasks,
                "accepted_tasks": int(accepted),
                "rejected_tasks": int(rejected),
                "state": new_state,
                "progress_version": 1,
                "progress_updated_at": now,
                "progress_done": 0,
                "progress_success": 0,
                "progress_failed": 0,
                "progress_cancelled": 0,
                "progress_skipped": 0,
                "progress_total": int(accepted),
            },
        )

        _insert_bulk_tasks(bid, bulk_tasks, now=now)

        conn.commit()

        snap = get_batch_snapshot(bid)
        qp = get_queue_position(bid, cid, pur) if snap and snap.get("state") == "queued" else None

        return {
            "mode": "created",
            "batch": snap,
            "active_batch": active_snap,
            "queue_position": qp,
            "need_enqueue": bool(snap and snap.get("state") == "running"),
        }


def list_queued_tasks_for_batch(batch_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()

    lim_sql = f"LIMIT {int(limit)}" if limit else ""
    cur.execute(
        f"""
        SELECT client_task_key,type,scope,symbol,freq,adjust,params_json
        FROM bulk_tasks
        WHERE batch_id=? AND status='queued'
        ORDER BY id ASC
        {lim_sql};
        """,
        (batch_id,),
    )
    rows = cur.fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        try:
            params = json.loads(r["params_json"]) if r["params_json"] else {}
            if not isinstance(params, dict):
                params = {}
        except Exception:
            params = {}

        out.append({
            "client_task_key": r["client_task_key"],
            "type": r["type"],
            "scope": r["scope"],
            "symbol": r["symbol"],
            "freq": r["freq"],
            "adjust": r["adjust"] or "none",
            "params": params,
        })
    return out


def mark_task_running(
    *,
    batch_id: str,
    client_task_key: str,
    last_task_id: Optional[str] = None,
) -> bool:
    bid = str(batch_id or "").strip()
    ckey = str(client_task_key or "").strip()
    if not bid or not ckey:
        return False

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE bulk_tasks
            SET status='running',
                last_task_id=?,
                updated_at=?
            WHERE batch_id=? AND client_task_key=? AND status='queued';
            """,
            (last_task_id, now, bid, ckey),
        )
        conn.commit()
        return cur.rowcount > 0


def _set_batch_state_locked(
    *,
    cur,
    batch_id: str,
    new_state: str,
    now: str,
    bump_version: bool,
) -> None:
    st = _safe_batch_state(new_state)

    if bump_version:
        cur.execute(
            """
            UPDATE bulk_batches
            SET state=?,
                progress_version=progress_version+1,
                progress_updated_at=?
            WHERE batch_id=?;
            """,
            (st, now, batch_id),
        )
    else:
        cur.execute(
            """
            UPDATE bulk_batches
            SET state=?,
                progress_updated_at=?
            WHERE batch_id=?;
            """,
            (st, now, batch_id),
        )


def _get_batch_row_locked(cur, batch_id: str):
    cur.execute("SELECT * FROM bulk_batches WHERE batch_id=? LIMIT 1;", (batch_id,))
    return cur.fetchone()


def _recompute_state_if_done_locked(cur, batch_id: str, now: str) -> Optional[str]:
    row = _get_batch_row_locked(cur, batch_id)
    if not row:
        return None

    total = int(row["progress_total"] or 0)
    if total <= 0:
        return None

    succ = int(row["progress_success"] or 0)
    fail = int(row["progress_failed"] or 0)
    canc = int(row["progress_cancelled"] or 0)
    skip = int(row["progress_skipped"] or 0)
    done = succ + fail + canc + skip

    if done < total:
        return None

    if fail > 0:
        new_state = "failed"
    elif canc > 0:
        new_state = "cancelled"
    else:
        # 全部成功或全部跳过或混合成功+跳过：都视为“完成成功”
        new_state = "success"

    if str(row["state"]).strip().lower() != new_state:
        _set_batch_state_locked(
            cur=cur,
            batch_id=batch_id,
            new_state=new_state,
            now=now,
            bump_version=True,
        )
        return new_state

    return str(row["state"]).strip().lower()


def finalize_task_terminal(
    *,
    batch_id: str,
    client_task_key: str,
    terminal_status: str,
    error_code: Optional[str],
    error_message: Optional[str],
) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    ckey = str(client_task_key or "").strip()
    st = _safe_task_status(terminal_status)
    if st not in ("success", "failed", "cancelled", "skipped"):
        st = "failed"

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        rowb = _get_batch_row_locked(cur, bid)
        if not rowb:
            return None

        cur.execute(
            """
            SELECT status FROM bulk_tasks
            WHERE batch_id=? AND client_task_key=?
            LIMIT 1;
            """,
            (bid, ckey),
        )
        r = cur.fetchone()
        if not r:
            conn.commit()
            return get_batch_snapshot(bid)

        prev = str(r["status"]).strip().lower()
        if prev in ("success", "failed", "cancelled", "skipped"):
            conn.commit()
            return get_batch_snapshot(bid)

        cur.execute(
            """
            UPDATE bulk_tasks
            SET status=?,
                last_error_code=?,
                last_error_message=?,
                updated_at=?
            WHERE batch_id=? AND client_task_key=? AND status IN ('queued','running');
            """,
            (st, error_code, error_message, now, bid, ckey),
        )

        if cur.rowcount <= 0:
            conn.commit()
            return get_batch_snapshot(bid)

        rowb2 = _get_batch_row_locked(cur, bid)
        succ = int(rowb2["progress_success"] or 0)
        fail = int(rowb2["progress_failed"] or 0)
        canc = int(rowb2["progress_cancelled"] or 0)
        skip = int(rowb2["progress_skipped"] or 0)

        if st == "success":
            succ += 1
        elif st == "failed":
            fail += 1
        elif st == "cancelled":
            canc += 1
        else:
            skip += 1

        done = succ + fail + canc + skip

        cur.execute(
            """
            UPDATE bulk_batches
            SET
              progress_version=progress_version+1,
              progress_updated_at=?,
              progress_success=?,
              progress_failed=?,
              progress_cancelled=?,
              progress_skipped=?,
              progress_done=?
            WHERE batch_id=?;
            """,
            (now, succ, fail, canc, skip, done, bid),
        )

        _recompute_state_if_done_locked(cur, bid, now)

        conn.commit()

    return get_batch_snapshot(bid)


def enter_stopping(
    *,
    batch_id: str,
    client_instance_id: str,
) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    cid = str(client_instance_id or "").strip()
    if not bid or not cid:
        return None

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT * FROM bulk_batches
            WHERE batch_id=? AND client_instance_id=?
            LIMIT 1;
            """,
            (bid, cid),
        )
        row = cur.fetchone()
        if not row:
            return None

        st = str(row["state"]).strip().lower()
        if st in ("success", "cancelled"):
            conn.commit()
            return _row_to_snapshot(row)

        if st != "stopping":
            _set_batch_state_locked(
                cur=cur,
                batch_id=bid,
                new_state="stopping",
                now=now,
                bump_version=True,
            )

        conn.commit()

    return get_batch_snapshot(bid)


def apply_stopping_sweep(
    *,
    batch_id: str,
    client_instance_id: str,
) -> Optional[Dict[str, Any]]:
    bid = str(batch_id or "").strip()
    cid = str(client_instance_id or "").strip()
    if not bid or not cid:
        return None

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM bulk_batches WHERE batch_id=? AND client_instance_id=? LIMIT 1;",
            (bid, cid),
        )
        row = cur.fetchone()
        if not row:
            return None

        state = str(row["state"]).strip().lower()
        if state in ("success", "cancelled"):
            conn.commit()
            return _row_to_snapshot(row)

        cur.execute(
            """
            UPDATE bulk_tasks
            SET status='cancelled',
                updated_at=?
            WHERE batch_id=? AND status='queued';
            """,
            (now, bid),
        )
        cancelled_count = int(cur.rowcount or 0)

        if cancelled_count > 0:
            rowb2 = _get_batch_row_locked(cur, bid)
            succ = int(rowb2["progress_success"] or 0)
            fail = int(rowb2["progress_failed"] or 0)
            canc = int(rowb2["progress_cancelled"] or 0)
            skip = int(rowb2["progress_skipped"] or 0)

            canc += cancelled_count
            done = succ + fail + canc + skip

            cur.execute(
                """
                UPDATE bulk_batches
                SET
                  progress_version=progress_version+1,
                  progress_updated_at=?,
                  progress_cancelled=?,
                  progress_done=?
                WHERE batch_id=?;
                """,
                (now, canc, done, bid),
            )

        _recompute_state_if_done_locked(cur, bid, now)

        conn.commit()

    return get_batch_snapshot(bid)


def resume_batch(
    *,
    batch_id: str,
    client_instance_id: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    bid = str(batch_id or "").strip()
    cid = str(client_instance_id or "").strip()
    if not bid or not cid:
        return None, "NOT_FOUND"

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM bulk_batches WHERE batch_id=? AND client_instance_id=? LIMIT 1;",
            (bid, cid),
        )
        row = cur.fetchone()
        if not row:
            return None, "NOT_FOUND"

        st = str(row["state"]).strip().lower()
        if st != "paused":
            conn.commit()
            return _row_to_snapshot(row), "BAD_STATE"

        _set_batch_state_locked(
            cur=cur,
            batch_id=bid,
            new_state="running",
            now=now,
            bump_version=True,
        )
        conn.commit()

    return get_batch_snapshot(bid), None


def retry_failed_reset(
    *,
    batch_id: str,
    client_instance_id: str,
    has_active: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    bid = str(batch_id or "").strip()
    cid = str(client_instance_id or "").strip()
    if not bid or not cid:
        return None, "NOT_FOUND"

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM bulk_batches WHERE batch_id=? AND client_instance_id=? LIMIT 1;",
            (bid, cid),
        )
        row = cur.fetchone()
        if not row:
            return None, "NOT_FOUND"

        cur.execute(
            """
            UPDATE bulk_tasks
            SET status='queued',
                attempts=attempts+1,
                last_error_code=NULL,
                last_error_message=NULL,
                updated_at=?
            WHERE batch_id=? AND status='failed';
            """,
            (now, bid),
        )
        reset_cnt = int(cur.rowcount or 0)

        if reset_cnt > 0:
            rowb2 = _get_batch_row_locked(cur, bid)
            succ = int(rowb2["progress_success"] or 0)
            fail = int(rowb2["progress_failed"] or 0)
            canc = int(rowb2["progress_cancelled"] or 0)
            skip = int(rowb2["progress_skipped"] or 0)

            fail = max(0, fail - reset_cnt)
            done = succ + fail + canc + skip

            cur.execute(
                """
                UPDATE bulk_batches
                SET
                  progress_version=progress_version+1,
                  progress_updated_at=?,
                  progress_failed=?,
                  progress_done=?
                WHERE batch_id=?;
                """,
                (now, fail, done, bid),
            )

        if has_active:
            cur.execute(
                """
                UPDATE bulk_batches
                SET
                  state='queued',
                  queue_ts=?,
                  progress_version=progress_version+1,
                  progress_updated_at=?
                WHERE batch_id=?;
                """,
                (now, now, bid),
            )
        else:
            _set_batch_state_locked(
                cur=cur,
                batch_id=bid,
                new_state="running",
                now=now,
                bump_version=True,
            )

        conn.commit()

    return get_batch_snapshot(bid), None


def tick_pick_next_queued(
    *,
    client_instance_id: str,
    purpose: str,
) -> Optional[Dict[str, Any]]:
    cid = str(client_instance_id or "").strip()
    pur = str(purpose or "").strip()
    if not cid or not pur:
        return None

    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT batch_id FROM bulk_batches
            WHERE client_instance_id=? AND purpose=?
              AND state IN ('running','paused','stopping')
            LIMIT 1;
            """,
            (cid, pur),
        )
        if cur.fetchone():
            return None

        cur.execute(
            """
            SELECT * FROM bulk_batches
            WHERE client_instance_id=? AND purpose=? AND state='queued'
            ORDER BY queue_ts ASC
            LIMIT 1;
            """,
            (cid, pur),
        )
        row = cur.fetchone()
        if not row:
            return None

        bid = str(row["batch_id"])

        _set_batch_state_locked(
            cur=cur,
            batch_id=bid,
            new_state="running",
            now=now,
            bump_version=True,
        )
        conn.commit()

    return get_batch_snapshot(bid)


def list_failed_tasks(
    *,
    batch_id: str,
    offset: int = 0,
    limit: int = 200,
) -> Tuple[int, List[Dict[str, Any]]]:
    bid = str(batch_id or "").strip()
    if not bid:
        return 0, []

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) AS n FROM bulk_tasks WHERE batch_id=? AND status='failed';",
        (bid,),
    )
    row = cur.fetchone()
    total = int(row["n"] or 0) if row else 0

    cur.execute(
        """
        SELECT
          client_task_key,
          type, scope, symbol, freq, adjust,
          attempts,
          last_error_code, last_error_message,
          updated_at
        FROM bulk_tasks
        WHERE batch_id=? AND status='failed'
        ORDER BY updated_at DESC, client_task_key ASC
        LIMIT ? OFFSET ?;
        """,
        (bid, int(limit), int(offset)),
    )
    rows = cur.fetchall()

    items = [dict(r) for r in rows]
    return total, items


def recover_incomplete_batches_to_paused(*, purpose: str = "after_hours") -> int:
    pur = str(purpose or "").strip() or "after_hours"
    now = now_iso()

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE bulk_batches
            SET
              state='paused',
              progress_version=progress_version+1,
              progress_updated_at=?
            WHERE purpose=?
              AND state IN ('running','stopping')
              AND progress_done < progress_total;
            """,
            (now, pur),
        )
        conn.commit()
        return int(cur.rowcount or 0)


def gc_delete_terminal_tasks(
    *,
    retention_days: int,
    purpose: str = "after_hours",
) -> int:
    try:
        days = max(0, int(retention_days))
    except Exception:
        days = 0

    if days <= 0:
        return 0

    pur = str(purpose or "").strip() or "after_hours"
    now_dt = datetime.fromisoformat(now_iso().replace("Z", "+00:00"))
    cutoff_dt = now_dt - timedelta(days=days)
    cutoff_iso = cutoff_dt.isoformat()

    deleted = 0

    with get_write_lock():
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT batch_id
            FROM bulk_batches
            WHERE purpose=?
              AND state IN ('success','cancelled')
              AND progress_failed=0
              AND progress_updated_at <= ?;
            """,
            (pur, cutoff_iso),
        )
        rows = cur.fetchall()
        batch_ids = [str(r["batch_id"]) for r in rows]

        for bid in batch_ids:
            cur.execute("DELETE FROM bulk_tasks WHERE batch_id=?;", (bid,))
            deleted += int(cur.rowcount or 0)

        conn.commit()

    return deleted


# ==============================================================================
# NEW: inflight 闸门支持
# ==============================================================================

def count_tasks_by_status(*, batch_id: str, status: str) -> int:
    """
    统计某批次下指定 status 的任务数（真相源查询）。

    用途：
      - inflight 闸门：统计 status='running' 的数量，保证 running <= limit
    """
    bid = str(batch_id or "").strip()
    st = _safe_task_status(status)
    if not bid:
        return 0

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) AS n FROM bulk_tasks WHERE batch_id=? AND status=?;",
        (bid, st),
    )
    row = cur.fetchone()
    return int(row["n"] or 0) if row else 0


def get_batch_state_for_client(*, batch_id: str, client_instance_id: str) -> Optional[str]:
    """
    查询批次状态（用于执行器执行前判断 stopping）。
    仅当 batch_id 与 client_instance_id 匹配时返回 state，否则返回 None（隔离不泄露）。
    """
    bid = str(batch_id or "").strip()
    cid = str(client_instance_id or "").strip()
    if not bid or not cid:
        return None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT state FROM bulk_batches WHERE batch_id=? AND client_instance_id=? LIMIT 1;",
        (bid, cid),
    )
    row = cur.fetchone()
    if not row:
        return None

    st = str(row["state"] or "").strip().lower()
    return st if st in _ALLOWED_BATCH_STATE else None
