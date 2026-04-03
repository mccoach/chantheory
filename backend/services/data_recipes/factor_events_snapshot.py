# backend/services/data_recipes/factor_events_snapshot.py
# ==============================
# factor_events_snapshot 任务配方（正式版）
#
# 正式语义：
#   - 全量解析 TDX 本地 gbbq
#   - 不做业务裁剪
#   - 落库为 gbbq_events_raw
#
# 说明：
#   - 本轮只完成“原始事件素材层”入库
#   - 不在本轮计算 factor 成品表
# ==============================

from __future__ import annotations

from typing import Dict, Any

import asyncio
import pandas as pd

from backend.datasource import dispatcher
from backend.db.data_task_status import (
    mark_data_task_running,
    mark_data_task_success,
    mark_data_task_failed,
)
from backend.db.gbbq_events import upsert_gbbq_events_raw
from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.factor_events_snapshot")


async def run_factor_events_snapshot(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id
    job_type = "sync_factor_events_snapshot"
    jobs_status: Dict[str, str] = {}
    total_rows = 0
    source_id = None

    mark_data_task_running("factor_events_snapshot")

    log_event(
        logger=_LOG,
        service="data_recipes.factor_events_snapshot",
        level="INFO",
        file=__file__,
        func="run_factor_events_snapshot",
        line=0,
        trace_id=trace_id,
        event="factor_events_snapshot.start",
        message="运行 factor_events_snapshot 配方",
        extra={"task_id": task.task_id},
    )

    try:
        raw_df, source_id = await dispatcher.fetch("gbbq_events_raw")

        if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
            jobs_status[job_type] = "failed"
            mark_data_task_failed("factor_events_snapshot", "gbbq_events_raw dataframe is empty")
            emit_job_finished(
                task,
                job_type=job_type,
                job_index=1,
                job_count=1,
                status="failed",
                result={
                    "rows": 0,
                    "message": "gbbq 原始事件快照同步失败：本地解析结果为空",
                    "error_code": "REMOTE_EMPTY",
                    "error_message": "gbbq_events_raw dataframe is empty",
                    "details": "local provider returned empty dataframe",
                    "extra": {"category": "gbbq_events_raw"},
                },
            )
        else:
            records = raw_df.to_dict("records")
            rows_written = await asyncio.to_thread(upsert_gbbq_events_raw, records)
            total_rows = int(rows_written or 0)

            jobs_status[job_type] = "success"
            mark_data_task_success("factor_events_snapshot")

            emit_job_finished(
                task,
                job_type=job_type,
                job_index=1,
                job_count=1,
                status="success",
                result={
                    "rows": total_rows,
                    "message": f"gbbq 原始事件快照已更新 {total_rows} 条记录",
                    "error_code": None,
                    "error_message": None,
                    "details": None,
                    "extra": {"source_id": source_id},
                },
            )

    except Exception as e:
        jobs_status[job_type] = "failed"
        mark_data_task_failed("factor_events_snapshot", str(e))

        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "gbbq 原始事件快照同步失败：内部异常",
                "error_code": "INTERNAL_ERROR",
                "error_message": str(e),
                "details": "exception in factor_events_snapshot recipe",
                "extra": {"exception_type": type(e).__name__},
            },
        )

        _LOG.error("[factor_events_snapshot配方] 同步异常: %s", e, exc_info=True)

    st = jobs_status.get(job_type)
    if st == "success":
        summary_msg = "factor_events_snapshot 成功"
        summary_code = None
        summary_err = None
    else:
        summary_msg = "factor_events_snapshot 失败"
        summary_code = "INTERNAL_ERROR"
        summary_err = "see job result"

    emit_task_finished(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary={
            "total_rows": total_rows,
            "message": summary_msg,
            "error_code": summary_code,
            "error_message": summary_err,
            "details": None,
            "extra": {"source_id": source_id},
        },
    )

    return {
        "updated": total_rows > 0,
        "source_id": source_id,
        "rows": total_rows,
    }
