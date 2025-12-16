# backend/services/data_recipes/kline.py
# ==============================
# 说明：current_kline 任务配方（K 线）
#
# 对应 Task：
#   type='current_kline', scope='symbol'
#
# Job 列表（重构后）：
#   1) sync_kline   （单一 Job，内部自带 gap_check + 远程拉取 + 落库）
#
# 特别约束：
#   - 股票：永远只同步/返回不复权数据（adjust='none'），即便 Task.adjust 为 qfq/hfq；
#   - 基金：根据 adjust 决定调用哪个子配方：
#       * 日/周/月：
#           - adjust='none' → F1: run_fund_dwm_unadj
#           - adjust='qfq'/'hfq' → F2: run_fund_dwm_adj
#       * 分时：
#           - adjust='none' → F3: run_fund_intraday_unadj
#           - adjust='qfq'/'hfq' → F4: run_fund_intraday_adj
#
# 日志 & 落库保证：
#   - 在 emit_task_done 之前调用 _writer.flush()，
#     确保所有 K 线写入已落库，task_done 发出后可以立即安全查询。
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional

from backend.services.task_model import Task
from backend.services.task_events import emit_job_done, emit_task_done
from backend.services.data_recipes.common import bool_param
from backend.services import bars_recipes
from backend.db.async_writer import get_async_writer
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.kline")
_writer = get_async_writer()


async def run_current_kline(task: Task) -> Dict[str, Any]:
    """
    current_kline 任务配方（Task：type='current_kline', scope='symbol'）

    Job 列表（重构后）：
      1) sync_kline

    设计原则：
      - 不再在 Task 层单独安排 gap_check Job；
      - sync_kline Job 内部根据 class/freq/adjust 选择对应的 bars_recipes.run_*，
        由各 recipe 自己完成：
          * gap_check（针对自身负责的数据集）
          * 远程拉取（dispatcher.fetch）
          * normalize + AsyncWriter 落库
      - force_fetch（Task.params.force_fetch）只在此一处作为“强制刷新”来源，
        并原样向下传递给对应 recipe。
    """
    trace_id = task.trace_id
    symbol = (task.symbol or "").strip()
    freq = (task.freq or "").strip()
    adjust_req = (task.adjust or "none").lower().strip()
    cls = (task.cls or "").strip().lower()
    force_fetch = bool_param(task, "force_fetch", False)

    job_types = ["sync_kline"]
    job_count = len(job_types)
    jobs_status: Dict[str, str] = {}
    total_rows: Optional[int] = None  # bars_recipes 未返回行数信息
    source_id: Optional[str] = None

    log_event(
        logger=_LOG,
        service="data_recipes.kline",
        level="INFO",
        file=__file__,
        func="run_current_kline",
        line=0,
        trace_id=trace_id,
        event="kline.start",
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

    # 参数校验
    if not symbol or not freq:
        jobs_status["sync_kline"] = "failed"
        emit_job_done(
            task,
            job_type="sync_kline",
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "current_kline 任务缺少 symbol 或 freq 参数",
                "error_code": "KLINE_PARAM_ERROR",
                "error_message": "symbol or freq missing",
            },
        )
        emit_task_done(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "current_kline 任务参数错误",
            },
        )
        return {"updated": False, "rows": 0, "source_id": None}

    # 股票的有效 adjust 永远为 'none'
    if cls == "stock":
        eff_adjust = "none"
    else:
        eff_adjust = adjust_req if adjust_req in ("none", "qfq", "hfq") else "none"

    job_type = "sync_kline"
    job_index = 1
    updated = False

    # ---- Job: sync_kline ----
    try:
        if cls not in ("stock", "fund"):
            jobs_status[job_type] = "failed"
            emit_job_done(
                task,
                job_type=job_type,
                job_index=job_index,
                job_count=job_count,
                status="failed",
                result={
                    "rows": 0,
                    "message": f"未识别的标的类别 class={cls}，仅支持 stock/fund",
                    "error_code": "KLINE_UNSUPPORTED_CLASS",
                    "error_message": f"class={cls}",
                },
            )
        else:
            # 实际执行 K 线同步（依赖 bars_recipes 内部的 gap_check）
            if cls == "stock":
                # 仅不复权
                if freq in ("1d", "1w", "1M"):
                    updated = await bars_recipes.run_stock_dwm_unadj(
                        symbol=symbol,
                        freq=freq,
                        force_fetch=force_fetch,
                        trace_id=trace_id,
                    )
                    source_id = "stock_dwm_unadj"
                elif freq in ("1m", "5m", "15m", "30m", "60m"):
                    updated = await bars_recipes.run_stock_intraday_unadj(
                        symbol=symbol,
                        freq=freq,
                        force_fetch=force_fetch,
                        trace_id=trace_id,
                    )
                    source_id = "stock_intraday_unadj"
                else:
                    jobs_status[job_type] = "failed"
                    emit_job_done(
                        task,
                        job_type=job_type,
                        job_index=job_index,
                        job_count=job_count,
                        status="failed",
                        result={
                            "rows": 0,
                            "message": f"不支持的 freq={freq}，当前仅支持 1m/5m/15m/30m/60m/1d/1w/1M",
                            "error_code": "KLINE_UNSUPPORTED_FREQ",
                            "error_message": f"freq={freq}",
                        },
                    )
                    # 后续不再 emit_task_done 内重复 emit_job_done
                    await _writer.flush()
                    emit_task_done(
                        task,
                        jobs=jobs_status,
                        completion_policy="all_required",
                        summary={
                            "total_rows": total_rows,
                            "message": "current_kline 任务失败：freq 不受支持",
                        },
                    )
                    return {
                        "updated": False,
                        "source_id": None,
                        "rows": total_rows,
                    }

            else:
                # cls == 'fund'
                if freq in ("1d", "1w", "1M"):
                    if eff_adjust == "none":
                        updated = await bars_recipes.run_fund_dwm_unadj(
                            symbol=symbol,
                            freq=freq,
                            force_fetch=force_fetch,
                            trace_id=trace_id,
                        )
                        source_id = "fund_dwm_unadj"
                    else:
                        updated = await bars_recipes.run_fund_dwm_adj(
                            symbol=symbol,
                            freq=freq,
                            adjust=eff_adjust,
                            force_fetch=force_fetch,
                            trace_id=trace_id,
                        )
                        source_id = f"fund_dwm_{eff_adjust}"
                elif freq in ("1m", "5m", "15m", "30m", "60m"):
                    if eff_adjust == "none":
                        updated = await bars_recipes.run_fund_intraday_unadj(
                            symbol=symbol,
                            freq=freq,
                            force_fetch=force_fetch,
                            trace_id=trace_id,
                        )
                        source_id = "fund_intraday_unadj"
                    else:
                        updated = await bars_recipes.run_fund_intraday_adj(
                            symbol=symbol,
                            freq=freq,
                            adjust=eff_adjust,
                            force_fetch=force_fetch,
                            trace_id=trace_id,
                        )
                        source_id = f"fund_intraday_{eff_adjust}"
                else:
                    jobs_status[job_type] = "failed"
                    emit_job_done(
                        task,
                        job_type=job_type,
                        job_index=job_index,
                        job_count=job_count,
                        status="failed",
                        result={
                            "rows": 0,
                            "message": f"不支持的 freq={freq}，当前仅支持 1m/5m/15m/30m/60m/1d/1w/1M",
                            "error_code": "KLINE_UNSUPPORTED_FREQ",
                            "error_message": f"freq={freq}",
                        },
                    )
                    await _writer.flush()
                    emit_task_done(
                        task,
                        jobs=jobs_status,
                        completion_policy="all_required",
                        summary={
                            "total_rows": total_rows,
                            "message": "current_kline 任务失败：freq 不受支持",
                        },
                    )
                    return {
                        "updated": False,
                        "source_id": None,
                        "rows": total_rows,
                    }

            # 根据 updated 标记结果
            if job_type not in jobs_status:
                # 正常执行路径
                if updated:
                    st2 = "success"
                    msg2 = "K 线已同步至最新"
                else:
                    # 未写入但流程成功完成
                    st2 = "success"
                    msg2 = "K 线同步流程已完成，本地可能已为最新（未写入新数据）"

                jobs_status[job_type] = st2
                emit_job_done(
                    task,
                    job_type=job_type,
                    job_index=job_index,
                    job_count=job_count,
                    status=st2,
                    result={
                        "rows": total_rows,
                        "message": msg2,
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
                "message": f"K 线同步异常：{e}",
                "error_code": "KLINE_SYNC_ERROR",
                "error_message": str(e),
            },
        )
        _LOG.error("[current_kline配方] 同步异常: %s", e, exc_info=True)

    # ---- Task 汇总 ----
    # 确保所有异步 K 线写入已落库，再发 task_done
    await _writer.flush()

    emit_task_done(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary={
            "total_rows": total_rows,
            "message": "current_kline 任务完成",
        },
    )

    return {
        "updated": jobs_status.get("sync_kline") == "success" and bool(updated),
        "source_id": source_id,
        "rows": total_rows,
    }