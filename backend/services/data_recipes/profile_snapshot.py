# backend/services/data_recipes/profile_snapshot.py
# ==============================
# profile_snapshot 任务配方（本地批量快照版）
#
# 设计原则：
#   - 不做缺口判断
#   - 触发即全量解析本地文件并批量写库
#   - 保持 task.finished / task.job.finished 事件语义
# ==============================

from __future__ import annotations

from typing import Dict, Any

import asyncio
import pandas as pd

from backend.datasource import dispatcher
from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.db.symbols import upsert_symbol_profile
from backend.services.normalizer import normalize_profile_snapshot_df
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.profile_snapshot")


async def run_profile_snapshot(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id
    job_type = "sync_profile_snapshot"
    jobs_status: Dict[str, str] = {}
    total_rows = 0
    source_id = None

    log_event(
        logger=_LOG,
        service="data_recipes.profile_snapshot",
        level="INFO",
        file=__file__,
        func="run_profile_snapshot",
        line=0,
        trace_id=trace_id,
        event="profile_snapshot.start",
        message="运行 profile_snapshot 配方（TDX本地批量版）",
        extra={"task_id": task.task_id},
    )

    try:
        raw_df, source_id = await dispatcher.fetch("profile_snapshot")

        if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
            jobs_status[job_type] = "failed"
            emit_job_finished(
                task,
                job_type=job_type,
                job_index=1,
                job_count=1,
                status="failed",
                result={
                    "rows": 0,
                    "message": "档案快照同步失败：本地解析结果为空",
                    "error_code": "REMOTE_EMPTY",
                    "error_message": "profile_snapshot raw dataframe is empty",
                    "details": "local provider returned empty dataframe",
                    "extra": {"category": "profile_snapshot"},
                },
            )
        else:
            clean_df = normalize_profile_snapshot_df(raw_df, source_tag="tdx_profile_snapshot")
            if clean_df is None or clean_df.empty:
                jobs_status[job_type] = "failed"
                emit_job_finished(
                    task,
                    job_type=job_type,
                    job_index=1,
                    job_count=1,
                    status="failed",
                    result={
                        "rows": 0,
                        "message": "档案快照同步失败：标准化后为空",
                        "error_code": "REMOTE_EMPTY",
                        "error_message": "normalized profile_snapshot is empty",
                        "details": "normalizer returned empty dataframe",
                        "extra": {"category": "profile_snapshot", "source_id": source_id},
                    },
                )
            else:
                records = clean_df.to_dict("records")
                rows_written = await asyncio.to_thread(upsert_symbol_profile, records)
                total_rows = int(rows_written or 0)
                jobs_status[job_type] = "success"
                emit_job_finished(
                    task,
                    job_type=job_type,
                    job_index=1,
                    job_count=1,
                    status="success",
                    result={
                        "rows": total_rows,
                        "message": f"档案快照已更新 {total_rows} 条记录",
                        "error_code": None,
                        "error_message": None,
                        "details": None,
                        "extra": {"source_id": source_id},
                    },
                )

    except Exception as e:
        jobs_status[job_type] = "failed"
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "档案快照同步失败：内部异常",
                "error_code": "INTERNAL_ERROR",
                "error_message": str(e),
                "details": "exception in profile_snapshot recipe",
                "extra": {"exception_type": type(e).__name__},
            },
        )
        _LOG.error("[profile_snapshot配方] 同步异常: %s", e, exc_info=True)

    st = jobs_status.get(job_type)
    if st == "success":
        summary_msg = "profile_snapshot 成功"
        summary_code = None
        summary_err = None
    else:
        summary_msg = "profile_snapshot 失败"
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
