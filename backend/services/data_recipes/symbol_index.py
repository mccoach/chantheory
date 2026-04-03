# backend/services/data_recipes/symbol_index.py
# ==============================
# 标的列表任务配方（symbol_index）
#
# 当前语义：
#   - 主数据源已切换为 TDX 本地文件解析
#   - 配方改为三市场并列：
#       * sync_sh_symbols
#       * sync_sz_symbols
#       * sync_bj_symbols
#   - 不再做缺口判断，始终执行三市场全量同步
#
# 本轮改动：
#   - 增加基础数据任务稳定状态写入
#   - 文件名按任务全名统一
# ==============================

from __future__ import annotations

from typing import Dict, Any

from backend.db.data_task_status import (
    mark_data_task_running,
    mark_data_task_success,
    mark_data_task_failed,
)
from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.services.sync_helper import fetch_normalize_save_symbol_index
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.symbol_index")

async def run_symbol_index(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id

    job_types = ["sync_sh_symbols", "sync_sz_symbols", "sync_bj_symbols"]
    jobs_status: Dict[str, str] = {}
    total_rows = 0

    mark_data_task_running("symbol_index")

    log_event(
        logger=_LOG,
        service="data_recipes.symbol_index",
        level="INFO",
        file=__file__,
        func="run_symbol_index",
        line=0,
        trace_id=trace_id,
        event="symbol_index.start",
        message="运行标的列表配方（TDX本地版）",
        extra={"task_id": task.task_id},
    )

    market_jobs = [
        ("sync_sh_symbols", "上交所标的", "symbol_list_sh", "tdx_sh_symbols", "SH"),
        ("sync_sz_symbols", "深交所标的", "symbol_list_sz", "tdx_sz_symbols", "SZ"),
        ("sync_bj_symbols", "北交所标的", "symbol_list_bj", "tdx_bj_symbols", "BJ"),
    ]

    idx = 1
    for job_type, display_name, category, source_tag, market in market_jobs:
        try:
            res = await fetch_normalize_save_symbol_index(
                category=category,
                display_name=display_name,
                source_tag=source_tag,
            )
            if res.get("status") == "success":
                c = int(res.get("count") or 0)
                total_rows += c
                st = "success"
                msg = f"{display_name} 同步成功，写入 {c} 条记录"
                code = None
                emsg = None
                details = None
            else:
                c = int(res.get("count") or 0)
                st = "failed"
                msg = f"{display_name} 同步失败"
                code = "INTERNAL_ERROR"
                emsg = str(res.get("error") or "")
                details = str(res.get("error") or "")
        except Exception as e:
            c = 0
            st = "failed"
            msg = f"{display_name} 同步失败：内部异常"
            code = "INTERNAL_ERROR"
            emsg = str(e)
            details = "exception in symbol_index recipe"
            _LOG.error("[标的列表配方] %s 同步异常: %s", display_name, e, exc_info=True)

        jobs_status[job_type] = st
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=idx,
            job_count=len(job_types),
            status=st,
            result={
                "rows": c,
                "message": msg,
                "error_code": code,
                "error_message": emsg,
                "details": details,
                "extra": {"market": market, "category": category, "source_tag": source_tag},
            },
        )
        idx += 1

    succ = sum(1 for v in jobs_status.values() if v == "success")
    fail = sum(1 for v in jobs_status.values() if v == "failed")
    if succ and not fail:
        overall_msg = f"symbol_index 全部成功，共写入 {total_rows} 条"
        overall_status = "success"
        overall_code = None
        overall_err = None
        mark_data_task_success("symbol_index")
    elif succ and fail:
        overall_msg = f"symbol_index 部分失败（成功 {succ}，失败 {fail}），共写入 {total_rows} 条"
        overall_status = "partial_fail"
        overall_code = "INTERNAL_ERROR"
        overall_err = "partial failure; see jobs"
        mark_data_task_failed("symbol_index", overall_err)
    else:
        overall_msg = "symbol_index 全部失败"
        overall_status = "failed"
        overall_code = "INTERNAL_ERROR"
        overall_err = "all jobs failed"
        mark_data_task_failed("symbol_index", overall_err)

    emit_task_finished(
        task,
        jobs=jobs_status,
        completion_policy="best_effort",
        summary={
            "total_rows": total_rows,
            "message": overall_msg,
            "error_code": overall_code,
            "error_message": overall_err,
            "details": None,
            "extra": {"success_jobs": succ, "failed_jobs": fail, "computed_overall": overall_status},
        },
    )

    return {
        "updated": total_rows > 0,
        "source_id": "TDX_LOCAL",
        "rows": total_rows,
    }