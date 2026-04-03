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
        "retryable": bool(int(row["retryable"] or 0) == 1),
        "cancelable": bool(int(row["cancelable"] or 0) == 1),
        "ui_message": row["ui_message"],
        "selection_signature": row["selection_signature"],
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
        "signal_code": row["signal_code"],
        "signal_message": row["signal_message"],
        "appended_rows": row["appended_rows"],
        "source_file_path": row["source_file_path"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }
