# backend/services/data_recipes/symbol.py
# ==============================
# 标的列表任务配方（symbol_index）
# 统一状态/错误码/SSE协议版
# ==============================

from __future__ import annotations

from typing import Dict, Any

from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.services.data_recipes.common import bool_param
from backend.services.normalizer import normalize_symbol_list_df
from backend.services.sync_helper import fetch_normalize_save
from backend.utils.logger import get_logger, log_event
from backend.db.connection import get_conn
from backend.utils.time import today_ymd, to_yyyymmdd_from_iso

_LOG = get_logger("data_recipes.symbol")


async def run_symbol_index(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id
    force_fetch = bool_param(task, "force_fetch", False)

    job_types = ["sync_sh_stock", "sync_sz_stock", "sync_sh_fund", "sync_sz_fund"]
    jobs_status: Dict[str, str] = {}
    total_rows = 0

    log_event(
        logger=_LOG,
        service="data_recipes.symbol",
        level="INFO",
        file=__file__,
        func="run_symbol_index",
        line=0,
        trace_id=trace_id,
        event="symbol_index.start",
        message="运行标的列表配方",
        extra={"task_id": task.task_id, "force_fetch": force_fetch},
    )

    conn = get_conn()

    def _subset_has_gap(market: str, cls: str) -> bool:
        if force_fetch:
            return True

        cur = conn.cursor()
        cur.execute(
            "SELECT MAX(updated_at) FROM symbol_index WHERE market=? AND class=?;",
            (market, cls),
        )
        result = cur.fetchone()
        if not result or not result[0]:
            return True

        try:
            updated_ymd = to_yyyymmdd_from_iso(result[0])
        except Exception:
            return True

        return updated_ymd < today_ymd()

    exchange_jobs = [
        ("sync_sh_stock", "上交所股票", "stock_list_sh", "sse_sh_stock", "SH", "stock"),
        ("sync_sz_stock", "深交所股票", "stock_list_sz", "szse_sz_stock", "SZ", "stock"),
        ("sync_sh_fund", "上交所基金", "fund_list_sh", "sse_sh_fund", "SH", "fund"),
        ("sync_sz_fund", "深交所基金", "fund_list_sz", "szse_sz_fund", "SZ", "fund"),
    ]

    idx = 1
    for job_type, display_name, category, source_tag, market, cls in exchange_jobs:
        has_gap = _subset_has_gap(market, cls)

        if not has_gap:
            jobs_status[job_type] = "success"
            emit_job_finished(
                task,
                job_type=job_type,
                job_index=idx,
                job_count=len(job_types),
                status="success",
                result={
                    "rows": 0,
                    "message": f"{display_name} 无需同步（本地已最新）",
                    "error_code": None,
                    "error_message": None,
                    "details": None,
                    "extra": {"market": market, "class": cls, "need_sync": False},
                },
            )
            idx += 1
            continue

        try:
            res = await fetch_normalize_save(
                category=category,
                normalizer=normalize_symbol_list_df,
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
                "extra": {"market": market, "class": cls, "category": category, "source_tag": source_tag},
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
    elif succ and fail:
        overall_msg = f"symbol_index 部分失败（成功 {succ}，失败 {fail}），共写入 {total_rows} 条"
        overall_status = "partial_fail"
        overall_code = "INTERNAL_ERROR"
        overall_err = "partial failure; see jobs"
    else:
        overall_msg = "symbol_index 全部失败"
        overall_status = "failed"
        overall_code = "INTERNAL_ERROR"
        overall_err = "all jobs failed"

    # task.finished 聚合（emit_task_finished 内部也会再聚合一次 overall_status，但 summary 仍需写清楚）
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
        "source_id": "SSE_SZSE",
        "rows": total_rows,
    }
