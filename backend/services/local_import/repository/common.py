# backend/services/local_import/repository/common.py
# ==============================
# 盘后数据导入 import - repository 内部公共工具
# ==============================

from __future__ import annotations

from typing import Dict, Any

_ALLOWED_BATCH_STATE = {"queued", "running", "paused", "success", "failed", "cancelled"}
_ALLOWED_TASK_STATE = {"queued", "running", "success", "failed", "cancelled"}


def _safe_batch_state(state: str) -> str:
    s = str(state or "").strip().lower()
    return s if s in _ALLOWED_BATCH_STATE else "queued"


def _safe_task_state(state: str) -> str:
    s = str(state or "").strip().lower()
    return s if s in _ALLOWED_TASK_STATE else "queued"


def _row_to_batch_dict(row) -> Dict[str, Any]:
    return {
        "batch_id": row["batch_id"],
        "state": row["state"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "progress_total": int(row["progress_total"] or 0),
        "progress_done": int(row["progress_done"] or 0),
        "progress_success": int(row["progress_success"] or 0),
        "progress_failed": int(row["progress_failed"] or 0),
        "progress_cancelled": int(row["progress_cancelled"] or 0),
        "retryable": bool(int(row["retryable"] or 0) == 1),
        "cancelable": bool(int(row["cancelable"] or 0) == 1),
        "ui_message": row["ui_message"],
    }


def _joined_row_to_task_dict(row) -> Dict[str, Any]:
    return {
        "market": str(row["market"] or "").strip().upper(),
        "symbol": str(row["symbol"] or "").strip(),
        "freq": row["freq"],
        "name": row["name"],
        "class": row["class"],
        "type": row["type"],
        "state": row["state"],
        "attempts": int(row["attempts"] or 0),
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "updated_at": row["updated_at"],
    }
