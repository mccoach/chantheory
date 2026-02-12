# backend/services/data_recipes/watchlist.py
# ==============================
# watchlist_update 任务配方（统一状态/错误码/SSE协议版）
# ==============================

from __future__ import annotations

from typing import Dict, Any, List

import asyncio

from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.db.watchlist import (
    insert_watchlist,
    delete_watchlist,
    select_user_watchlist_with_details,
)
from backend.utils.logger import get_logger

_LOG = get_logger("data_recipes.watchlist")


async def run_watchlist_update(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id
    symbol = (task.symbol or "").strip()
    action = (task.params.get("action") or "").strip().lower()
    tags = task.params.get("tags") or []
    sort_order = int(task.params.get("sort_order") or 0)

    job_type = "apply_watchlist_update"
    jobs_status: Dict[str, str] = {}

    if not symbol:
        jobs_status[job_type] = "failed"
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "自选更新失败：缺少 symbol 参数",
                "error_code": "INVALID_PARAMS",
                "error_message": "symbol missing",
                "details": None,
                "extra": {"action": action},
            },
        )
        emit_task_finished(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "watchlist_update 失败：参数错误",
                "error_code": "INVALID_PARAMS",
                "error_message": "symbol missing",
                "details": None,
                "extra": {"action": action},
            },
        )
        return {
            "updated": False,
            "action": action,
            "rows": 0,
            "items": [],
            "status": "failed",
            "error_code": "INVALID_PARAMS",
            "error_message": "symbol missing",
        }

    if action not in ("add", "remove"):
        jobs_status[job_type] = "failed"
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "自选更新失败：action 不支持",
                "error_code": "INVALID_PARAMS",
                "error_message": f"unsupported action={action}",
                "details": "supported: add/remove",
                "extra": {"action": action},
            },
        )
        emit_task_finished(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "watchlist_update 失败：action 不支持",
                "error_code": "INVALID_PARAMS",
                "error_message": f"unsupported action={action}",
                "details": None,
                "extra": {"action": action},
            },
        )
        return {
            "updated": False,
            "action": action,
            "rows": 0,
            "items": [],
            "status": "failed",
            "error_code": "INVALID_PARAMS",
            "error_message": f"unsupported action={action}",
        }

    _LOG.info(
        "[watchlist_update配方] action=%s symbol=%s tags=%s sort_order=%s task_id=%s",
        action, symbol, tags, sort_order, task.task_id
    )

    rows_changed = 0
    items: List[Dict[str, Any]] = []
    status = "failed"
    code = None
    emsg = None
    details = None
    msg = ""

    try:
        if action == "add":
            ok = await asyncio.to_thread(
                insert_watchlist,
                symbol=symbol,
                source="manual",
                note=None,
                tags=tags,
                sort_order=sort_order,
            )
            if not ok:
                status = "failed"
                code = "DB_WRITE_FAILED"
                emsg = "insert_watchlist returned False"
                msg = "自选添加失败"
            else:
                status = "success"
                rows_changed = 1
                msg = "已添加到自选池"

        else:  # remove
            ok = await asyncio.to_thread(delete_watchlist, symbol)
            if not ok:
                status = "failed"
                code = "INVALID_PARAMS"
                emsg = "symbol not in watchlist"
                msg = "标的不在自选池中"
            else:
                status = "success"
                rows_changed = 1
                msg = "已从自选池移除"

        try:
            items = await asyncio.to_thread(select_user_watchlist_with_details)
        except Exception as e_list:
            _LOG.error("[watchlist_update配方] 查询最新自选列表异常: %s", e_list, exc_info=True)
            items = items or []

    except Exception as e:
        status = "failed"
        code = "INTERNAL_ERROR"
        emsg = str(e)
        details = "exception in watchlist_update recipe"
        msg = "自选更新失败：内部异常"
        _LOG.error("[watchlist_update配方] 执行异常: %s", e, exc_info=True)
        try:
            items = await asyncio.to_thread(select_user_watchlist_with_details)
        except Exception:
            items = []

    jobs_status[job_type] = status

    emit_job_finished(
        task,
        job_type=job_type,
        job_index=1,
        job_count=1,
        status=status,
        result={
            "rows": rows_changed,
            "message": msg,
            "error_code": code,
            "error_message": emsg,
            "details": details,
            "extra": {"action": action, "items": items},
        },
    )

    emit_task_finished(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary={
            "total_rows": rows_changed,
            "message": "watchlist_update 成功" if status == "success" else "watchlist_update 失败",
            "error_code": code if status != "success" else None,
            "error_message": emsg if status != "success" else None,
            "details": details,
            "extra": {"action": action, "items": items},
        },
    )

    return {
        "updated": status == "success",
        "action": action,
        "rows": rows_changed,
        "items": items,
        "status": status,
        "error_code": code,
        "error_message": emsg,
        "source_id": "db.watchlist",
    }
