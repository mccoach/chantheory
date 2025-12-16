# backend/services/sync_helper.py
# ==============================
# 说明：同步任务通用辅助函数（V3.0 - 列表专用·SSE/SZSE 版）
#
# 当前职责：
#   - 为“标的列表”提供一个可复用的 "fetch → normalize → upsert_symbol_index" 流程；
#   - 每步详细日志（用于诊断）；
#   - 构造 SSE 进度事件由 symbol_sync 使用。
#
# 重要约束：
#   - 仅适用于 symbol_index 列表同步：
#       * category: 'stock_list_sh' / 'stock_list_sz' / 'fund_list_sh' / 'fund_list_sz'
#       * normalizer: normalize_symbol_list_df(raw_df, source_tag=...)
#   - 不再混入其他业务（如 profile/日历等）。
# ==============================

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable, Dict, Any

from backend.datasource import dispatcher
from backend.db.symbols import upsert_symbol_index
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("sync_helper")


async def fetch_normalize_save(
    category: str,
    normalizer: Callable,   # normalize_symbol_list_df
    display_name: str,
    source_tag: str,        # 'sse_sh_stock'/'szse_sz_stock'/'sse_sh_fund'/'szse_sz_fund'
) -> Dict[str, Any]:
    """
    通用的“标的列表 拉取-标准化-落库”流程（SSE/SZSE 专用）。

    Args:
        category: dispatcher category（如 'stock_list_sh'）
        normalizer: 标准化函数（normalize_symbol_list_df）
        display_name: 显示名称（用于日志）
        source_tag: 传给 normalizer 的 source_tag，用于决定 market/class/type/board 映射

    Returns:
        dict: {
            'status': 'success' | 'failed',
            'count': int,
            'error': str (失败时),
        }
    """
    try:
        # ===== 步骤1：拉取 =====
        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.fetch.start",
            message=f"[同步] {display_name} 开始拉取...",
            extra={"category": category, "display_name": display_name},
        )

        raw_df, source_id = await dispatcher.fetch(category)

        if raw_df is None or raw_df.empty:
            error_msg = f"{display_name}拉取为空"
            log_event(
                logger=_LOG, service="sync_helper", level="ERROR",
                file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
                event="sync.fetch.empty",
                message=f"[同步] {error_msg}",
                extra={"category": category, "source_id": source_id},
            )
            return {"status": "failed", "count": 0, "error": error_msg}

        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.fetch.success",
            message=f"[同步] {display_name} 拉取成功：{len(raw_df)} 行",
            extra={
                "category": category,
                "source_id": source_id,
                "rows": len(raw_df),
                "columns": raw_df.columns.tolist(),
            },
        )

        # ===== 步骤2：标准化 =====
        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.normalize.start",
            message=f"[同步] {display_name} 开始标准化...",
            extra={"category": category, "source_tag": source_tag},
        )

        clean_df = normalizer(raw_df, source_tag=source_tag)

        if clean_df is None or clean_df.empty:
            error_msg = f"{display_name}标准化失败"
            log_event(
                logger=_LOG, service="sync_helper", level="ERROR",
                file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
                event="sync.normalize.empty",
                message=f"[同步] {error_msg}",
                extra={"category": category, "source_tag": source_tag},
            )
            return {"status": "failed", "count": 0, "error": error_msg}

        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.normalize.success",
            message=f"[同步] {display_name} 标准化成功：{len(clean_df)} 行",
            extra={
                "category": category,
                "rows": len(clean_df),
                "sample": clean_df.head(3).to_dict("records"),
            },
        )

        # ===== 步骤3：落库 symbol_index =====
        records = clean_df.to_dict("records")

        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.save.start",
            message=f"[同步] {display_name} 开始落库：{len(records)} 条",
            extra={"category": category, "rows": len(records)},
        )

        try:
            row_count = await asyncio.to_thread(upsert_symbol_index, records)
            log_event(
                logger=_LOG, service="sync_helper", level="INFO",
                file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
                event="sync.save.success",
                message=f"[同步] {display_name} 落库成功：影响 {row_count} 行",
                extra={
                    "category": category,
                    "rows_inserted": len(records),
                    "rows_affected": row_count,
                },
            )
        except Exception as db_error:
            error_msg = f"{display_name}落库失败: {type(db_error).__name__}: {db_error}"
            log_event(
                logger=_LOG, service="sync_helper", level="ERROR",
                file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
                event="sync.save.fail",
                message=f"[同步] {error_msg}",
                extra={
                    "category": category,
                    "error_type": type(db_error).__name__,
                    "error_message": str(db_error),
                },
            )
            return {"status": "failed", "count": 0, "error": error_msg}

        # ===== 步骤4：成功返回 =====
        log_event(
            logger=_LOG, service="sync_helper", level="INFO",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.complete",
            message=f"[同步] {display_name}：{len(records)} 个 ✅",
            extra={"category": category, "count": len(records)},
        )

        return {"status": "success", "count": len(records)}

    except Exception as e:
        error_msg = f"{display_name}整体异常: {type(e).__name__}: {e}"
        log_event(
            logger=_LOG, service="sync_helper", level="ERROR",
            file=__file__, func="fetch_normalize_save", line=0, trace_id=None,
            event="sync.exception",
            message=f"[同步] {error_msg}",
            extra={
                "category": category,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        return {"status": "failed", "count": 0, "error": error_msg}