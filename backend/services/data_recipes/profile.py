# backend/services/data_recipes/profile.py
# ==============================
# 说明：current_profile 任务配方（档案）
#
# 对应 Task：
#   type='current_profile', scope='symbol'
#
# Job 列表（重构后）：
#   1) sync_profile
#
# 特别说明：
#   - 档案使用 AsyncWriter 写入 symbol_profile；
#   - sync_profile Job 内部负责：
#       * 调用 check_info_updated_today 判断是否需要更新；
#       * 根据 force_fetch / 缺口结果决定是否调用 profile_sync.fetch_profile_snapshot；
#       * 写入 symbol_profile；
#   - 在 emit_task_done 之前调用 _writer.flush()，
#     确保 task_done 发出后档案数据已落库，可立即安全查询。
# ==============================

from __future__ import annotations

from typing import Dict, Any

from backend.services.task_model import Task
from backend.services.task_events import emit_job_done, emit_task_done
from backend.services.data_recipes.common import bool_param
from backend.services import profile_sync
from backend.db.async_writer import get_async_writer
from backend.utils.gap_checker import check_info_updated_today
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.profile")
_writer = get_async_writer()


async def run_current_profile(task: Task) -> Dict[str, Any]:
    """
    current_profile 任务配方（Task：type='current_profile', scope='symbol'）

    Job 列表：
      1) sync_profile
    """
    trace_id = task.trace_id
    symbol = (task.symbol or "").strip()
    force_fetch = bool_param(task, "force_fetch", False)

    job_types = ["sync_profile"]
    job_count = len(job_types)
    jobs_status: Dict[str, str] = {}

    log_event(
        logger=_LOG,
        service="data_recipes.profile",
        level="INFO",
        file=__file__,
        func="run_current_profile",
        line=0,
        trace_id=trace_id,
        event="profile.start",
        message="运行 current_profile 配方",
        extra={
            "task_id": task.task_id,
            "symbol": symbol,
            "force_fetch": force_fetch,
        },
    )

    job_type = "sync_profile"
    job_index = 1
    rows_written = 0
    updated = False

    # ---- Job: sync_profile ----
    try:
        need_sync = True
        if not force_fetch:
            need_sync = check_info_updated_today(
                symbol=symbol,
                data_type_id="current_profile",
            )

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
                    "message": "档案已在今日更新，本次未执行同步",
                },
            )
        else:
            snapshot = await profile_sync.fetch_profile_snapshot(symbol)
            if not snapshot:
                jobs_status[job_type] = "failed"
                emit_job_done(
                    task,
                    job_type=job_type,
                    job_index=job_index,
                    job_count=job_count,
                    status="failed",
                    result={
                        "rows": 0,
                        "message": "档案拉取失败或为空",
                        "error_code": "PROFILE_SYNC_ERROR",
                        "error_message": "snapshot is empty",
                    },
                )
            else:
                # 异步写入 symbol_profile
                await _writer.write_profile(snapshot)
                rows_written = 1
                updated = True
                jobs_status[job_type] = "success"
                emit_job_done(
                    task,
                    job_type=job_type,
                    job_index=job_index,
                    job_count=job_count,
                    status="success",
                    result={
                        "rows": rows_written,
                        "message": "档案已同步至最新",
                        "error_code": None,
                        "error_message": None,
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
                "message": f"档案同步异常：{e}",
                "error_code": "PROFILE_SYNC_ERROR",
                "error_message": str(e),
            },
        )
        _LOG.error("[current_profile配方] 同步异常: %s", e, exc_info=True)

    # 确保档案写入已全部落库，再发 task_done
    await _writer.flush()

    emit_task_done(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary={
            "total_rows": rows_written,
            "message": "current_profile 任务完成",
        },
    )

    return {
        "updated": updated and jobs_status.get("sync_profile") == "success",
        "source_id": "SSE_SZSE",
        "rows": rows_written,
    }
