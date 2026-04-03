# backend/services/data_recipes/current_kline.py
# ==============================
# current_kline 任务配方（第一阶段：仅稳定支持日线）
#
# 本轮改动：
#   - 文件名按任务全名统一
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional

from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.services.data_recipes.common import bool_param
from backend.services import bars_recipes
from backend.db.async_writer import get_async_writer
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.current_kline")
_writer = get_async_writer()


def _primary_error(
    *,
    error_code: str,
    error_message: str | None,
    details: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "error_code": str(error_code),
        "error_message": str(error_message) if error_message is not None else None,
        "details": str(details) if details is not None else None,
        "extra": extra or {},
    }


async def run_current_kline(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id
    symbol = (task.symbol or "").strip()
    freq = (task.freq or "").strip()
    adjust_req = (task.adjust or "none").lower().strip()
    cls = (task.cls or "").strip().lower()
    force_fetch = bool_param(task, "force_fetch", False)

    job_type = "sync_kline"
    jobs_status: Dict[str, str] = {}
    total_rows: Optional[int] = None
    source_id: Optional[str] = None

    log_event(
        logger=_LOG,
        service="data_recipes.current_kline",
        level="INFO",
        file=__file__,
        func="run_current_kline",
        line=0,
        trace_id=trace_id,
        event="current_kline.start",
        message="运行 current_kline 配方",
        extra={
            "task_id": task.task_id,
            "symbol": symbol,
            "freq": freq,
            "adjust": adjust_req,
            "class": cls,
            "force_fetch": force_fetch,
        },
    )

    if not symbol or not freq:
        pe = _primary_error(
            error_code="INVALID_PARAMS",
            error_message="symbol or freq missing",
        )
        jobs_status[job_type] = "failed"
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "K线任务参数错误：缺少 symbol 或 freq",
                **pe,
            },
        )
        emit_task_finished(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "current_kline 失败：参数错误",
                **pe,
                "extra": {"primary_error": pe, "symbol": symbol, "freq": freq},
            },
        )
        return {"updated": False, "rows": 0, "source_id": None}

    if cls == "stock":
        eff_adjust = "none"
    else:
        eff_adjust = adjust_req if adjust_req in ("none", "qfq", "hfq") else "none"

    updated = False
    pe: Optional[Dict[str, Any]] = None

    try:
        if cls not in ("stock", "fund"):
            jobs_status[job_type] = "skipped"
            pe = _primary_error(
                error_code="INVALID_PARAMS",
                error_message=f"class={cls}",
                details="current_kline only supports stock/fund",
                extra={"class": cls},
            )
            emit_job_finished(
                task,
                job_type=job_type,
                job_index=1,
                job_count=1,
                status="skipped",
                result={
                    "rows": 0,
                    "message": "因系统规则不支持，该任务已跳过",
                    **pe,
                },
            )

        else:
            if freq != "1d":
                jobs_status[job_type] = "skipped"
                pe = _primary_error(
                    error_code="UNSUPPORTED_IN_CURRENT_STAGE",
                    error_message=f"freq={freq}",
                    details="current stage only supports 1d stable db chain",
                    extra={"freq": freq, "class": cls},
                )
                emit_job_finished(
                    task,
                    job_type=job_type,
                    job_index=1,
                    job_count=1,
                    status="skipped",
                    result={
                        "rows": 0,
                        "message": "当前阶段仅支持日线（1d）同步，分钟线后续将切换到归档链路",
                        **pe,
                    },
                )
                await _writer.flush()
                emit_task_finished(
                    task,
                    jobs=jobs_status,
                    completion_policy="all_required",
                    summary={
                        "total_rows": 0,
                        "message": "current_kline 已跳过：当前阶段仅支持 1d",
                        **pe,
                        "extra": {"primary_error": pe, "freq": freq},
                    },
                )
                return {"updated": False, "source_id": None, "rows": total_rows}

            if cls == "stock":
                updated = await bars_recipes.run_stock_dwm_unadj(
                    symbol=symbol,
                    freq=freq,
                    force_fetch=force_fetch,
                    trace_id=trace_id,
                )
                source_id = "stock_day_unadj"
            else:
                jobs_status[job_type] = "skipped"
                pe = _primary_error(
                    error_code="UNSUPPORTED_IN_CURRENT_STAGE",
                    error_message=f"class={cls} freq={freq}",
                    details="fund day chain is not enabled in current stage",
                    extra={"freq": freq, "class": cls},
                )
                emit_job_finished(
                    task,
                    job_type=job_type,
                    job_index=1,
                    job_count=1,
                    status="skipped",
                    result={
                        "rows": 0,
                        "message": "当前阶段基金日线链路未启用",
                        **pe,
                    },
                )
                await _writer.flush()
                emit_task_finished(
                    task,
                    jobs=jobs_status,
                    completion_policy="all_required",
                    summary={
                        "total_rows": 0,
                        "message": "current_kline 已跳过：基金日线链路未启用",
                        **pe,
                        "extra": {"primary_error": pe, "freq": freq, "class": cls},
                    },
                )
                return {"updated": False, "source_id": None, "rows": total_rows}

            if job_type not in jobs_status:
                jobs_status[job_type] = "success"
                emit_job_finished(
                    task,
                    job_type=job_type,
                    job_index=1,
                    job_count=1,
                    status="success",
                    result={
                        "rows": total_rows,
                        "message": "日线已同步至最新" if updated else "日线无需同步（本地已最新）",
                        "error_code": None,
                        "error_message": None,
                        "details": None,
                        "extra": {"updated": bool(updated), "source_id": source_id},
                    },
                )

    except bars_recipes.RemoteEmptyDataError as e:
        jobs_status[job_type] = "failed"
        pe = _primary_error(
            error_code="REMOTE_EMPTY",
            error_message=str(e),
            details="remote fetch returned empty or normalized empty",
            extra={"symbol": symbol, "freq": freq, "class": cls},
        )
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "K线同步失败：远端返回空数据（强规则）",
                **pe,
            },
        )
    except Exception as e:
        jobs_status[job_type] = "failed"
        pe = _primary_error(
            error_code="INTERNAL_ERROR",
            error_message=str(e),
            details="exception in current_kline recipe",
            extra={"exception_type": type(e).__name__},
        )
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "K线同步失败：内部异常",
                **pe,
            },
        )
        _LOG.error("[current_kline配方] 同步异常: %s", e, exc_info=True)

    await _writer.flush()

    st = jobs_status.get(job_type)
    if st == "success":
        summary = {
            "total_rows": total_rows,
            "message": "current_kline 成功",
            "error_code": None,
            "error_message": None,
            "details": None,
            "extra": {
                "primary_error": None,
                "symbol": symbol,
                "freq": freq,
                "source_id": source_id,
                "updated": bool(updated),
            },
        }
    elif st == "skipped":
        pe = pe or _primary_error(error_code="INVALID_PARAMS", error_message="skipped by rule")
        summary = {
            "total_rows": 0,
            "message": "current_kline 已跳过",
            **pe,
            "extra": {"primary_error": pe, "symbol": symbol, "freq": freq, "class": cls},
        }
    else:
        pe = pe or _primary_error(error_code="INTERNAL_ERROR", error_message="unknown error")
        summary = {
            "total_rows": 0,
            "message": "current_kline 失败",
            **pe,
            "extra": {"primary_error": pe, "symbol": symbol, "freq": freq, "source_id": source_id},
        }

    emit_task_finished(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary=summary,
    )

    return {
        "updated": jobs_status.get(job_type) == "success" and bool(updated),
        "source_id": source_id,
        "rows": total_rows,
    }
