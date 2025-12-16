# backend/services/data_recipes/watchlist.py
# ==============================
# 说明：watchlist_update 任务配方（自选池更新）
#
# 对应 Task：
#   type='watchlist_update', scope='symbol'
#
# Job 列表：
#   1) apply_watchlist_update
#
# params:
#   - action: 'add' / 'remove'
#   - tags: list[str]（仅 add 时用）
#   - sort_order: int（仅 add 时用）
# ==============================

from __future__ import annotations

from typing import Dict, Any, List

import asyncio

from backend.services.task_model import Task
from backend.services.task_events import emit_job_done, emit_task_done
from backend.db.watchlist import (
    insert_watchlist,
    delete_watchlist,
    select_user_watchlist_with_details,
)
from backend.utils.logger import get_logger

_LOG = get_logger("data_recipes.watchlist")


async def run_watchlist_update(task: Task) -> Dict[str, Any]:
    """
    watchlist_update 任务配方（Task：type='watchlist_update', scope='symbol'）

    Job 列表：
      1) apply_watchlist_update
    """
    trace_id = task.trace_id
    symbol = (task.symbol or "").strip()
    action = (task.params.get("action") or "").strip().lower()
    tags = task.params.get("tags") or []
    sort_order = int(task.params.get("sort_order") or 0)

    job_type = "apply_watchlist_update"
    job_index = 1
    job_count = 1
    jobs_status: Dict[str, str] = {}

    if not symbol:
        jobs_status[job_type] = "failed"
        emit_job_done(
            task,
            job_type=job_type,
            job_index=job_index,
            job_count=job_count,
            status="failed",
            result={
                "rows": 0,
                "message": "watchlist_update 任务缺少 symbol 参数",
                "error_code": "WATCHLIST_PARAM_ERROR",
                "error_message": "symbol missing",
                "action": action,
                "items": [],
            },
        )
        emit_task_done(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "watchlist_update 任务失败：参数错误",
                "action": action,
                "items": [],
            },
        )
        return {
            "updated": False,
            "action": action,
            "rows": 0,
            "items": [],
            "status": "failed",
            "error_code": "WATCHLIST_PARAM_ERROR",
            "error_message": "symbol missing",
        }

    if action not in ("add", "remove"):
        jobs_status[job_type] = "failed"
        emit_job_done(
            task,
            job_type=job_type,
            job_index=job_index,
            job_count=job_count,
            status="failed",
            result={
                "rows": 0,
                "message": f"watchlist_update 不支持的 action={action}",
                "error_code": "WATCHLIST_ACTION_ERROR",
                "error_message": f"action={action}",
                "action": action,
                "items": [],
            },
        )
        emit_task_done(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "watchlist_update 任务失败：action 非法",
                "action": action,
                "items": [],
            },
        )
        return {
            "updated": False,
            "action": action,
            "rows": 0,
            "items": [],
            "status": "failed",
            "error_code": "WATCHLIST_ACTION_ERROR",
            "error_message": f"action={action}",
        }

    _LOG.info(
        "[watchlist_update配方] 开始执行 action=%s symbol=%s tags=%s sort_order=%s task_id=%s",
        action,
        symbol,
        tags,
        sort_order,
        task.task_id,
    )

    rows_changed = 0
    items: List[Dict[str, Any]] = []
    status = "failed"
    err_code = None
    err_msg = None
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
                err_code = "WATCHLIST_INSERT_FAILED"
                err_msg = "insert_watchlist returned False"
                msg = "添加自选失败"
            else:
                status = "success"
                rows_changed = 1
                msg = "已添加到自选池"

        elif action == "remove":
            ok = await asyncio.to_thread(delete_watchlist, symbol)
            if not ok:
                status = "failed"
                err_code = "WATCHLIST_NOT_FOUND"
                err_msg = "symbol not in watchlist"
                msg = "标的不在自选池中"
            else:
                status = "success"
                rows_changed = 1
                msg = "已从自选池移除"

        # 无论成功失败，都尝试刷新最新列表
        try:
            items = await asyncio.to_thread(select_user_watchlist_with_details)
        except Exception as e_list:
            _LOG.error("[watchlist_update配方] 查询最新自选列表异常: %s",
                       e_list,
                       exc_info=True)
            if not items:
                items = []

    except Exception as e:
        status = "failed"
        err_code = "WATCHLIST_EXCEPTION"
        err_msg = str(e)
        msg = f"自选更新异常：{e}"
        _LOG.error("[watchlist_update配方] 执行异常: %s", e, exc_info=True)
        try:
            items = await asyncio.to_thread(select_user_watchlist_with_details)
        except Exception:
            items = []

    jobs_status[job_type] = status

    emit_job_done(
        task,
        job_type=job_type,
        job_index=job_index,
        job_count=job_count,
        status=status,
        result={
            "rows": rows_changed,
            "message": msg,
            "error_code": err_code,
            "error_message": err_msg,
            "action": action,
            "items": items,
        },
    )

    emit_task_done(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary={
            "total_rows": rows_changed,
            "message": "自选池更新成功" if status == "success" else "自选池更新失败",
            "action": action,
            "items": items,
        },
    )

    return {
        "updated": status == "success",
        "action": action,
        "rows": rows_changed,
        "items": items,
        "status": status,
        "error_code": err_code,
        "error_message": err_msg,
        "source_id": "db.watchlist",
    }
