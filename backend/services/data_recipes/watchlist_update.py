# backend/services/data_recipes/watchlist_update.py
# ==============================
# watchlist_update 任务配方（统一状态/错误码/SSE协议双主键最终版）
#
# 本轮改动：
#   - watchlist 正式升级为 (symbol, market) 双主键体系
#   - 不再允许 symbol-only 自选更新
#   - 直接输出最终错误码，避免中间层二次转译
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
from backend.db.symbols import select_symbol_index
from backend.utils.logger import get_logger

_LOG = get_logger("data_recipes.watchlist_update")

async def run_watchlist_update(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id
    symbol = (task.symbol or "").strip()
    market = str(task.market or "").strip().upper()
    action = (task.params.get("action") or "").strip().lower()
    tags = task.params.get("tags") or []
    sort_order = int(task.params.get("sort_order") or 0)

    job_type = "apply_watchlist_update"
    jobs_status: Dict[str, str] = {}

    if not symbol or not market:
        jobs_status[job_type] = "failed"
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "自选更新失败：缺少 symbol 或 market 参数",
                "error_code": "WATCHLIST_PARAM_ERROR",
                "error_message": "symbol or market missing",
                "details": None,
                "extra": {"action": action, "symbol": symbol, "market": market},
            },
        )
        emit_task_finished(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "watchlist_update 失败：参数错误",
                "error_code": "WATCHLIST_PARAM_ERROR",
                "error_message": "symbol or market missing",
                "details": None,
                "extra": {"action": action, "symbol": symbol, "market": market, "items": []},
            },
        )
        return {
            "updated": False,
            "action": action,
            "rows": 0,
            "items": [],
            "status": "failed",
            "error_code": "WATCHLIST_PARAM_ERROR",
            "error_message": "symbol or market missing",
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
                "error_code": "WATCHLIST_ACTION_ERROR",
                "error_message": f"unsupported action={action}",
                "details": "supported: add/remove",
                "extra": {"action": action, "symbol": symbol, "market": market},
            },
        )
        emit_task_finished(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "watchlist_update 失败：action 不支持",
                "error_code": "WATCHLIST_ACTION_ERROR",
                "error_message": f"unsupported action={action}",
                "details": None,
                "extra": {"action": action, "symbol": symbol, "market": market, "items": []},
            },
        )
        return {
            "updated": False,
            "action": action,
            "rows": 0,
            "items": [],
            "status": "failed",
            "error_code": "WATCHLIST_ACTION_ERROR",
            "error_message": f"unsupported action={action}",
        }

    _LOG.info(
        "[watchlist_update配方] action=%s symbol=%s market=%s tags=%s sort_order=%s task_id=%s",
        action, symbol, market, tags, sort_order, task.task_id
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
            symbol_rows = await asyncio.to_thread(
                select_symbol_index,
                symbol=symbol,
                market=market,
            )
            if not symbol_rows:
                status = "failed"
                code = "WATCHLIST_SYMBOL_NOT_FOUND"
                emsg = f"symbol not found in symbol_index: {market}.{symbol}"
                msg = "标的不存在，无法加入自选池"
            else:
                ok = await asyncio.to_thread(
                    insert_watchlist,
                    symbol=symbol,
                    market=market,
                    source="manual",
                    note=None,
                    tags=tags,
                    sort_order=sort_order,
                )
                if not ok:
                    status = "failed"
                    code = "WATCHLIST_INSERT_FAILED"
                    emsg = "insert_watchlist returned False"
                    msg = "自选添加失败"
                else:
                    status = "success"
                    rows_changed = 1
                    msg = "已添加到自选池"

        else:  # remove
            ok = await asyncio.to_thread(delete_watchlist, symbol, market)
            if not ok:
                status = "failed"
                code = "WATCHLIST_NOT_FOUND"
                emsg = f"watchlist item not found: {market}.{symbol}"
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
        code = "WATCHLIST_EXCEPTION"
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
            "extra": {
                "action": action,
                "symbol": symbol,
                "market": market,
                "items": items,
            },
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
            "extra": {
                "action": action,
                "symbol": symbol,
                "market": market,
                "items": items,
            },
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