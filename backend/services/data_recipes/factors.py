# backend/services/data_recipes/factors.py
# ==============================
# 说明：current_factors 任务配方（复权因子）
#
# 对应 Task：
#   type='current_factors', scope='symbol'
#
# Job 列表（重构后）：
#   1) sync_factors
#
# 设计说明：
#   - 不再单独设置 gap_check Job；
#   - sync_factors Job 内部负责：
#       * 对因子数据 D(symbol, date) 做是否“今日已更新”的判断；
#       * 根据 force_fetch / 缺口结果决定是否调用 bars_recipes.run_stock_factors；
#       * 使用 AsyncWriter 写入 adj_factors；
#   - emit_task_done 前调用 _writer.flush()，确保落库后即可安全查询。
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional

from backend.services.task_model import Task
from backend.services.task_events import emit_job_done, emit_task_done
from backend.services.data_recipes.common import bool_param
from backend.services import bars_recipes
from backend.db.async_writer import get_async_writer
from backend.utils.gap_checker import check_info_updated_today
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.factors")
_writer = get_async_writer()


async def run_current_factors(task: Task) -> Dict[str, Any]:
    """
    current_factors 任务配方（Task：type='current_factors', scope='symbol'）

    Job 列表：
      1) sync_factors

    说明：
      - 仅支持股票标的（class='stock'），其他标的直接失败；
      - sync_factors Job 内先做“是否今日已更新”的判断，
        若未更新或 force_fetch=True，则调用 bars_recipes.run_stock_factors
        进行同步。
    """
    trace_id = task.trace_id
    symbol = (task.symbol or "").strip()
    cls = (task.cls or "").strip().lower()
    force_fetch = bool_param(task, "force_fetch", False)

    job_types = ["sync_factors"]
    job_count = len(job_types)
    jobs_status: Dict[str, str] = {}

    # 非股票标的：直接失败
    if cls != "stock":
        jobs_status["sync_factors"] = "failed"
        emit_job_done(
            task,
            job_type="sync_factors",
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": f"current_factors 仅支持股票标的，当前 class={cls or 'None'}",
                "error_code": "FACTORS_UNSUPPORTED_CLASS",
                "error_message": f"class={cls}",
            },
        )
        emit_task_done(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "current_factors 任务失败：非股票标的",
            },
        )
        return {"updated": False, "rows": 0, "source_id": None}

    log_event(
        logger=_LOG,
        service="data_recipes.factors",
        level="INFO",
        file=__file__,
        func="run_current_factors",
        line=0,
        trace_id=trace_id,
        event="factors.start",
        message="运行 current_factors 配方",
        extra={
            "task_id": task.task_id,
            "symbol": symbol,
            "force_fetch": force_fetch,
        },
    )

    job_type = "sync_factors"
    job_index = 1
    updated = False

    # ---- Job: sync_factors ----
    try:
        need_sync = True
        if not force_fetch:
            # check_info_updated_today 返回 True 表示“有缺口”（未更新到今日）
            need_sync = check_info_updated_today(
                symbol=symbol,
                data_type_id="current_factors",
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
                    "message": "因子已在今日更新，本次未执行同步",
                },
            )
        else:
            ok = await bars_recipes.run_stock_factors(
                symbol=symbol,
                force_fetch=force_fetch,
                trace_id=trace_id,
            )
            updated = bool(ok)
            st = "success"
            msg = "因子已同步至最新" if updated else "因子同步流程已完成（本地可能已为最新）"

            jobs_status[job_type] = st
            emit_job_done(
                task,
                job_type=job_type,
                job_index=job_index,
                job_count=job_count,
                status=st,
                result={
                    "rows": None,
                    "message": msg,
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
                "message": f"因子同步异常：{e}",
                "error_code": "FACTORS_SYNC_ERROR",
                "error_message": str(e),
            },
        )
        _LOG.error("[current_factors配方] 同步异常: %s", e, exc_info=True)

    # 确保因子写入已全部落库，再发 task_done
    await _writer.flush()

    emit_task_done(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary={
            "total_rows": None,
            "message": "current_factors 任务完成",
        },
    )

    return {
        "updated": updated and jobs_status.get("sync_factors") == "success",
        "source_id": "baostock.get_adj_factors",
        "rows": None,
    }