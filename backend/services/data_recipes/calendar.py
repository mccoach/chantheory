# backend/services/data_recipes/calendar.py
# ==============================
# 交易日历任务配方（trade_calendar）
# 统一状态/错误码/SSE协议版
# ==============================

from __future__ import annotations

from typing import Dict, Any

import asyncio
import pandas as pd

from backend.settings import settings
from backend.datasource import dispatcher
from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.db.calendar import upsert_trade_calendar
from backend.services.data_recipes.common import bool_param
from backend.services.normalizer import normalize_trade_calendar_df
from backend.utils.gap_checker import check_calendar_gap
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.calendar")


async def run_trade_calendar(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id
    force_fetch = bool_param(task, "force_fetch", False)

    job_type = "sync_calendar"
    jobs_status: Dict[str, str] = {}
    total_rows = 0
    source_id = None

    log_event(
        logger=_LOG,
        service="data_recipes.calendar",
        level="INFO",
        file=__file__,
        func="run_trade_calendar",
        line=0,
        trace_id=trace_id,
        event="calendar.start",
        message="运行交易日历配方",
        extra={
            "task_id": task.task_id,
            "force_fetch": force_fetch,
        },
    )

    try:
        need_sync = True
        if not force_fetch:
            need_sync = check_calendar_gap()

        if not need_sync:
            jobs_status[job_type] = "success"
            emit_job_finished(
                task,
                job_type=job_type,
                job_index=1,
                job_count=1,
                status="success",
                result={
                    "rows": 0,
                    "message": "交易日历无需同步（本地已最新）",
                    "error_code": None,
                    "error_message": None,
                    "details": None,
                    "extra": {"need_sync": False},
                },
            )
        else:
            raw_df, source_id = await dispatcher.fetch("trade_calendar")

            # 强规则：真实远程拉取为空 => failed
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
                        "message": "交易日历同步失败：远端返回空数据（强规则）",
                        "error_code": "REMOTE_EMPTY",
                        "error_message": "remote trade_calendar empty",
                        "details": "remote fetch returned empty",
                        "extra": {"category": "trade_calendar"},
                    },
                )
            else:
                clean_df = normalize_trade_calendar_df(raw_df)
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
                            "message": "交易日历同步失败：标准化后为空（强规则）",
                            "error_code": "REMOTE_EMPTY",
                            "error_message": "normalized trade_calendar empty",
                            "details": "normalized dataframe is empty",
                            "extra": {"category": "trade_calendar", "source_id": source_id},
                        },
                    )
                else:
                    records = [
                        {
                            "date": int(row["date"]),
                            "market": settings.default_market,
                            "is_trading_day": 1,
                        }
                        for _, row in clean_df.iterrows()
                    ]
                    rows_written = await asyncio.to_thread(upsert_trade_calendar, records)
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
                            "message": f"交易日历已更新 {total_rows} 条记录",
                            "error_code": None,
                            "error_message": None,
                            "details": None,
                            "extra": {"need_sync": True, "source_id": source_id},
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
                "message": "交易日历同步失败：内部异常",
                "error_code": "INTERNAL_ERROR",
                "error_message": str(e),
                "details": "exception in trade_calendar recipe",
                "extra": {"exception_type": type(e).__name__},
            },
        )
        _LOG.error("[日历配方] 同步异常: %s", e, exc_info=True)

    # task.finished
    st = jobs_status.get(job_type)
    if st == "success":
        summary_msg = "trade_calendar 成功"
        summary_code = None
        summary_err = None
    else:
        summary_msg = "trade_calendar 失败"
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
        "updated": bool(total_rows),
        "source_id": source_id,
        "rows": total_rows,
    }
