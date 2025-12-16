# backend/services/data_recipes/calendar.py
# ==============================
# 说明：交易日历任务配方（trade_calendar）
#
# 对应 Task：
#   type='trade_calendar', scope='global'
#
# Job 列表（重构后）：
#   1) sync_calendar
# ==============================

from __future__ import annotations

from typing import Dict, Any

import asyncio
import pandas as pd

from backend.settings import settings
from backend.datasource import dispatcher
from backend.services.task_model import Task
from backend.services.task_events import emit_job_done, emit_task_done
from backend.db.calendar import upsert_trade_calendar
from backend.services.data_recipes.common import bool_param
from backend.services.normalizer import normalize_trade_calendar_df
from backend.utils.gap_checker import check_calendar_gap
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.calendar")


async def run_trade_calendar(task: Task) -> Dict[str, Any]:
    """
    交易日历任务配方（Task：type='trade_calendar', scope='global'）

    Job 列表（重构后）：
      1) sync_calendar

    行为：
      - sync_calendar Job 内部负责：
          * 使用 check_calendar_gap 判断是否需要刷新；
          * 根据 force_fetch / 缺口结果决定是否调用 dispatcher.fetch('trade_calendar')；
          * normalize + upsert_trade_calendar；
          * 发送 job_done 与 task_done 事件。
    """
    trace_id = task.trace_id
    force_fetch = bool_param(task, "force_fetch", False)
    job_types = ["sync_calendar"]
    job_count = len(job_types)
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

    job_type = "sync_calendar"
    job_index = 1

    # ---- Job: sync_calendar ----
    try:
        need_sync = True
        if not force_fetch:
            need_sync = check_calendar_gap()

        if not need_sync:
            jobs_status[job_type] = "success"
            emit_job_done(
                task,
                job_type=job_type,
                job_index=job_index,
                job_count=job_count,
                status="success",
                result={
                    "rows": 0,
                    "message": "本地交易日历已为最新，本次未执行远程同步",
                },
            )
        else:
            raw_df, source_id = await dispatcher.fetch("trade_calendar")

            if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
                jobs_status[job_type] = "failed"
                emit_job_done(
                    task,
                    job_type=job_type,
                    job_index=job_index,
                    job_count=job_count,
                    status="failed",
                    result={
                        "rows": 0,
                        "message": "远程返回空交易日历数据，保持本地现状",
                        "error_code": "CALENDAR_EMPTY_REMOTE",
                        "error_message": "remote trade_calendar empty",
                    },
                )
            else:
                clean_df = normalize_trade_calendar_df(raw_df)
                if clean_df is None or clean_df.empty:
                    jobs_status[job_type] = "failed"
                    emit_job_done(
                        task,
                        job_type=job_type,
                        job_index=job_index,
                        job_count=job_count,
                        status="failed",
                        result={
                            "rows": 0,
                            "message": "交易日历标准化后无有效数据，保持本地现状",
                            "error_code": "CALENDAR_NORMALIZE_EMPTY",
                            "error_message": "normalized trade_calendar empty",
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
                    total_rows = rows_written
                    jobs_status[job_type] = "success"
                    emit_job_done(
                        task,
                        job_type=job_type,
                        job_index=job_index,
                        job_count=job_count,
                        status="success",
                        result={
                            "rows": rows_written,
                            "message": f"交易日历已更新 {rows_written} 条记录",
                        },
                    )

    except Exception as e:
        jobs_status[job_type] = "failed"
        emit_job_done(
            task,
            job_type=job_type,
            job_index=job_index,
            job_count=job_count,
            status="failed",
            result={
                "rows": 0,
                "message": f"交易日历同步异常：{e}",
                "error_code": "CALENDAR_SYNC_ERROR",
                "error_message": str(e),
            },
        )
        _LOG.error("[日历配方] 同步异常: %s", e, exc_info=True)

    # ---- Task 汇总 ----
    msg_summary = (
        "交易日历已是最新，无需更新"
        if (jobs_status.get(job_type) == "success" and total_rows == 0)
        else "交易日历同步完成"
    )
    emit_task_done(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary={
            "total_rows": total_rows,
            "message": msg_summary,
        },
    )

    return {
        "updated": bool(total_rows),
        "source_id": source_id,
        "rows": total_rows,
    }