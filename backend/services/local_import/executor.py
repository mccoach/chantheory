# backend/services/local_import/executor.py
# ==============================
# 盘后数据导入 import - 单文件执行器
#
# 职责：
#   - 执行单个文件任务
#   - 路径定位
#   - 全量读取文件
#   - 全量解析
#   - 全量标准化
#   - 单事务批量 upsert 写库
#
# 关键原则：
#   - 一次文件任务 = 一个完整原子执行单元
#   - 不边解析边写库
#   - 不边读边写库
#   - 仅在最终 records 准备完成后，一次性单事务 upsert
# ==============================

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Any

from backend.datasource.local_files.tdx_day import load_tdx_day_df
from backend.db.candles import upsert_candles_raw
from backend.services.normalizer import normalize_tdx_day_df_to_candles_records
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("local_import.executor")


def _execute_day_file_sync(
    *,
    file_path: str,
    market: str,
    symbol: str,
) -> int:
    """
    同步执行单个 .day 文件导入，并返回写入记录数。
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"import file not found: {path}")

    raw_df = load_tdx_day_df(path)
    records = normalize_tdx_day_df_to_candles_records(
        raw_df,
        symbol=symbol,
        market=market,
    )

    if not records:
        raise ValueError(f"no valid records after parsing/normalizing: {path}")

    written = upsert_candles_raw(records)
    return int(written or 0)


async def execute_import_file_task(
    *,
    batch_id: str,
    market: str,
    symbol: str,
    freq: str,
    file_path: str,
) -> Dict[str, Any]:
    """
    异步执行单个导入文件任务。

    Returns:
        {
          "rows": int,
          "error_code": str | None,
          "error_message": str | None,
        }

    Raises:
        Exception:
            由调用方统一转任务终态 failed
    """
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()
    f = str(freq or "").strip()

    if f != "1d":
        raise ValueError(f"unsupported freq for local import executor: {f}")

    log_event(
        logger=_LOG,
        service="local_import.executor",
        level="INFO",
        file=__file__,
        func="execute_import_file_task",
        line=0,
        trace_id=None,
        event="local_import.file.start",
        message="start import file task",
        extra={
            "batch_id": batch_id,
            "market": m,
            "symbol": s,
            "freq": f,
            "file_path": file_path,
        },
    )

    rows = await asyncio.to_thread(
        _execute_day_file_sync,
        file_path=file_path,
        market=m,
        symbol=s,
    )

    log_event(
        logger=_LOG,
        service="local_import.executor",
        level="INFO",
        file=__file__,
        func="execute_import_file_task",
        line=0,
        trace_id=None,
        event="local_import.file.done",
        message="import file task done",
        extra={
            "batch_id": batch_id,
            "market": m,
            "symbol": s,
            "freq": f,
            "rows": rows,
            "file_path": file_path,
        },
    )

    return {
        "rows": rows,
        "error_code": None,
        "error_message": None,
    }
