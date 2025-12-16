# backend/services/data_recipes/symbol.py
# ==============================
# 说明：标的列表任务配方（symbol_index）
#
# 对应 Task：
#   type='symbol_index', scope='global'
#
# Job 列表（重构后）：
#   1) sync_sh_stock  : 上交所股票列表
#   2) sync_sz_stock  : 深交所股票列表
#   3) sync_sh_fund   : 上交所基金列表
#   4) sync_sz_fund   : 深交所基金列表
#
# 设计要点：
#   - 不再设置全局 gap_check Job；
#   - 每个 sync_* Job 内部对“自己负责的子集”做缺口判断：
#       * sync_sh_stock : market='SH', class='stock'
#       * sync_sz_stock : market='SZ', class='stock'
#       * sync_sh_fund  : market='SH', class='fund'
#       * sync_sz_fund  : market='SZ', class='fund'
#     缺口判断逻辑：
#       - 查询该子集在 symbol_index 中的 MAX(updated_at)
#       - 比较日期是否 < 今日
#       - 若 force_fetch=True，则无条件视为“有缺口”
#   - 若该子集无缺口，则本次 Job 不调用远程接口，直接标记成功，rows=0。
#   - 真正的远程 fetch/normalize/upsert 由 fetch_normalize_save 完成（不再包含 gap_check）。
# ==============================

from __future__ import annotations

from typing import Dict, Any

from backend.services.task_model import Task
from backend.services.task_events import emit_job_done, emit_task_done
from backend.services.data_recipes.common import bool_param
from backend.services.normalizer import normalize_symbol_list_df
from backend.services.sync_helper import fetch_normalize_save
from backend.utils.logger import get_logger, log_event
from backend.db.connection import get_conn
from backend.utils.time import today_ymd, to_yyyymmdd_from_iso

_LOG = get_logger("data_recipes.symbol")


async def run_symbol_index(task: Task) -> Dict[str, Any]:
    """
    标的列表任务配方（Task：type='symbol_index', scope='global'）

    Job 列表：
      1) sync_sh_stock
      2) sync_sz_stock
      3) sync_sh_fund
      4) sync_sz_fund

    completion_policy: "best_effort"
    """
    trace_id = task.trace_id
    force_fetch = bool_param(task, "force_fetch", False)
    job_types = [
        "sync_sh_stock", "sync_sz_stock", "sync_sh_fund", "sync_sz_fund"
    ]
    job_count = len(job_types)
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
        extra={
            "task_id": task.task_id,
            "force_fetch": force_fetch,
        },
    )

    conn = get_conn()

    def _subset_has_gap(market: str, cls: str) -> bool:
        """
        针对某个子集（market + class）做缺口判断：
          - force_fetch=True → 无条件视为有缺口；
          - 否则：
              * SELECT MAX(updated_at) FROM symbol_index WHERE market=? AND class=?;
              * 若无数据/解析失败 → 有缺口；
              * 若日期 < 今日 → 有缺口；
              * 否则无缺口。
        """
        if force_fetch:
            return True

        cur = conn.cursor()
        cur.execute(
            "SELECT MAX(updated_at) FROM symbol_index WHERE market=? AND class=?;",
            (market, cls),
        )
        result = cur.fetchone()
        if not result or not result[0]:
            _LOG.debug(
                "[缺口] 标的子集无数据 → 有缺口 market=%s class=%s",
                market,
                cls,
            )
            return True

        try:
            updated_at = result[0]
            updated_ymd = to_yyyymmdd_from_iso(updated_at)
        except Exception as e:
            _LOG.debug(
                "[缺口] 标的子集时间解析失败 → 有缺口 market=%s class=%s error=%s",
                market,
                cls,
                e,
            )
            return True

        today = today_ymd()
        has_gap = updated_ymd < today

        _LOG.debug(
            "[缺口] 标的子集 market=%s class=%s 更新日期=%s 今日=%s → %s",
            market,
            cls,
            updated_ymd,
            today,
            "有缺口" if has_gap else "无缺口",
        )
        return has_gap

    # ---- 四类同步 ----
    exchange_jobs = [
        ("sync_sh_stock", "上交所股票", "stock_list_sh", "sse_sh_stock",
         "SH", "stock"),
        ("sync_sz_stock", "深交所股票", "stock_list_sz", "szse_sz_stock",
         "SZ", "stock"),
        ("sync_sh_fund", "上交所基金", "fund_list_sh", "sse_sh_fund",
         "SH", "fund"),
        ("sync_sz_fund", "深交所基金", "fund_list_sz", "szse_sz_fund",
         "SZ", "fund"),
    ]

    idx = 1
    for job_type, display_name, category, source_tag, market, cls in exchange_jobs:
        has_gap = _subset_has_gap(market, cls)

        # 无缺口：视为成功，rows=0
        if not has_gap:
            jobs_status[job_type] = "success"
            emit_job_done(
                task,
                job_type=job_type,
                job_index=idx,
                job_count=job_count,
                status="success",
                result={
                    "rows": 0,
                    "message": f"{display_name} 已为最新，本次未刷新",
                },
            )
            idx += 1
            continue

        # 需要刷新：执行 fetch_normalize_save
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
                err_code = None
                err_msg = None
            else:
                c = int(res.get("count") or 0)
                st = "failed"
                msg = f"{display_name} 同步失败：{res.get('error')}"
                err_code = "SYMBOL_INDEX_SYNC_ERROR"
                err_msg = str(res.get("error"))
        except Exception as e:
            c = 0
            st = "failed"
            msg = f"{display_name} 同步异常：{e}"
            err_code = "SYMBOL_INDEX_SYNC_EXCEPTION"
            err_msg = str(e)
            _LOG.error("[标的列表配方] %s 同步异常: %s", display_name, e, exc_info=True)

        jobs_status[job_type] = st
        emit_job_done(
            task,
            job_type=job_type,
            job_index=idx,
            job_count=job_count,
            status=st,
            result={
                "rows": c,
                "message": msg,
                "error_code": err_code,
                "error_message": err_msg,
            },
        )
        idx += 1

    # ---- Task 汇总 ----
    # best_effort：允许部分失败
    succ = sum(1 for v in jobs_status.values() if v == "success")
    fail = sum(1 for v in jobs_status.values() if v == "failed")
    if succ and not fail:
        msg_summary = f"标的列表同步全部成功，共 {total_rows} 条记录"
    elif succ and fail:
        msg_summary = f"标的列表同步部分失败（成功 {succ} 步，失败 {fail} 步），共写入 {total_rows} 条记录"
    else:
        msg_summary = "标的列表同步全部失败"

    emit_task_done(
        task,
        jobs=jobs_status,
        completion_policy="best_effort",
        summary={
            "total_rows": total_rows,
            "message": msg_summary,
        },
    )

    return {
        "updated": total_rows > 0,
        "source_id": "SSE_SZSE",
        "rows": total_rows,
    }