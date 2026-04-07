# backend/services/data_recipes/current_kline.py
# ==============================
# current_kline 任务配方（正式版）
#
# 新语义：
#   - 保障当前标的基础行情尽量完备
#   - 总是先保 1d
#   - 总是尝试保证 factor
#   - 若请求分钟族，再保 1m / 5m
# ==============================

from __future__ import annotations

from typing import Dict, Any

from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.services.freq_mapper import map_request_freq
from backend.services.bars_recipes import (
    ensure_local_day_bars,
    ensure_local_1m_bars,
    ensure_local_5m_bars,
    ensure_local_factors,
)
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.current_kline")


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
    market = (task.market or "").strip().upper()
    freq = (task.freq or "").strip()
    adjust_req = (task.adjust or "none").lower().strip()

    job_type = "ensure_current_kline"
    jobs_status: Dict[str, str] = {}

    if not symbol or not market or not freq:
        pe = _primary_error(
            error_code="INVALID_PARAMS",
            error_message="symbol / market / freq missing",
        )
        jobs_status[job_type] = "failed"
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={"rows": 0, "message": "参数错误", **pe},
        )
        emit_task_finished(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={"total_rows": 0, "message": "current_kline 失败", **pe},
        )
        return {"updated": False, "rows": 0}

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
            "market": market,
            "freq": freq,
            "adjust": adjust_req,
        },
    )

    mapping = map_request_freq(freq)
    updated = False
    rows = 0
    message = ""

    try:
        day_result = await ensure_local_day_bars(
            market=market,
            code=symbol,
            refresh_interval_seconds=None,
        )
        day_df = day_result["df"]
        updated = updated or bool(day_result["updated"])

        factor_result = await ensure_local_factors(
            market=market,
            code=symbol,
            day_df=day_df,
            request_adjust=adjust_req,
        )
        if factor_result.get("message"):
            message = factor_result["message"]

        if mapping["need_minute"]:
            if mapping["base_minute_freq"] == "1m":
                minute_result = await ensure_local_1m_bars(
                    market=market,
                    code=symbol,
                    refresh_interval_seconds=None,
                )
            else:
                minute_result = await ensure_local_5m_bars(
                    market=market,
                    code=symbol,
                    refresh_interval_seconds=None,
                )
            updated = updated or bool(minute_result["updated"])
            rows = len(minute_result["df"]) if minute_result.get("df") is not None else 0
            if minute_result.get("gap_message"):
                message = minute_result["gap_message"]
        else:
            rows = len(day_df) if day_df is not None else 0
            if day_result.get("gap_message"):
                message = day_result["gap_message"]

        jobs_status[job_type] = "success"
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="success",
            result={
                "rows": rows,
                "message": message or "基础行情保障完成",
                "error_code": None,
                "error_message": None,
                "details": None,
                "extra": {"updated": bool(updated)},
            },
        )

        emit_task_finished(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": rows,
                "message": "current_kline 成功",
                "error_code": None,
                "error_message": None,
                "details": None,
                "extra": {"updated": bool(updated)},
            },
        )

        return {"updated": updated, "rows": rows}

    except Exception as e:
        pe = _primary_error(
            error_code="INTERNAL_ERROR",
            error_message=str(e),
            details="exception in current_kline recipe",
            extra={"exception_type": type(e).__name__},
        )
        jobs_status[job_type] = "failed"
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={"rows": 0, "message": "基础行情保障失败", **pe},
        )
        emit_task_finished(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={"total_rows": 0, "message": "current_kline 失败", **pe},
        )
        return {"updated": False, "rows": 0}
