# backend/services/local_import/executor.py
# ==============================
# 盘后数据导入 import - 单文件执行器
#
# 当前阶段职责：
#   - 执行单个导入文件任务
#   - 统一分流：
#       * 1d -> SQLite 日线真相源
#       * 1m -> 分钟线累积归档 .lc1
#       * 5m -> 分钟线累积归档 .lc5
#
# 关键原则：
#   - 一次文件任务 = 一个完整原子执行单元
#   - 日线：解析 -> 标准化 -> DB
#   - 分钟线：解析 -> 标准化 -> minute_archive
#   - 状态机与进度规则完全沿用日线
#
# 本轮改动（任务追溯返回）：
#   - error_code / warning_code 收敛为 signal_code
#   - error_message / warning_message 收敛为 signal_message
#   - 返回：
#       * appended_rows
#       * source_file_path
#   - 不再返回 final_total_rows
# ==============================

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Any

from backend.datasource.local_files.tdx_day import load_tdx_day_df
from backend.datasource.local_files.tdx_minute import load_tdx_minute_df
from backend.db.candles import upsert_candles_day_raw
from backend.services.normalizer import (
    normalize_tdx_day_df_to_candles_records,
    normalize_tdx_minute_df_to_archive_records,
)
from backend.services.minute_archive import merge_and_write_minute_archive


def _execute_day_file_sync(
    *,
    file_path: str,
    market: str,
    symbol: str,
) -> Dict[str, Any]:
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

    written = upsert_candles_day_raw(records)
    return {
        "appended_rows": int(written or 0),
    }


def _execute_minute_file_sync(
    *,
    file_path: str,
    market: str,
    symbol: str,
    freq: str,
) -> Dict[str, Any]:
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"import file not found: {path}")

    raw_df = load_tdx_minute_df(path)
    records = normalize_tdx_minute_df_to_archive_records(
        raw_df,
        symbol=symbol,
        market=market,
        freq=freq,
    )

    if not records:
        raise ValueError(f"no valid minute records after parsing/normalizing: {path}")

    result = merge_and_write_minute_archive(
        market=market,
        symbol=symbol,
        freq=freq,
        records=records,
    )
    return {
        "appended_rows": int(result.get("appended_rows") or 0),
        "signal_code": result.get("warning_code"),
        "signal_message": result.get("warning_message"),
    }


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

    当前阶段支持：
      - 1d <- .day  -> SQLite
      - 1m <- .lc1  -> minute_archive
      - 5m <- .lc5  -> minute_archive

    Returns:
        {
          "appended_rows": int,
          "signal_code": str | None,
          "signal_message": str | None,
          "source_file_path": str,
        }

    Raises:
        Exception:
            由调用方统一转任务终态 failed
    """
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()
    f = str(freq or "").strip()
    p = str(Path(file_path).resolve())

    if f == "1d":
        result = await asyncio.to_thread(
            _execute_day_file_sync,
            file_path=file_path,
            market=m,
            symbol=s,
        )
        return {
            "appended_rows": int(result.get("appended_rows") or 0),
            "signal_code": None,
            "signal_message": None,
            "source_file_path": p,
        }

    if f in ("1m", "5m"):
        result = await asyncio.to_thread(
            _execute_minute_file_sync,
            file_path=file_path,
            market=m,
            symbol=s,
            freq=f,
        )
        return {
            "appended_rows": int(result.get("appended_rows") or 0),
            "signal_code": result.get("signal_code"),
            "signal_message": result.get("signal_message"),
            "source_file_path": p,
        }

    raise ValueError(f"unsupported freq for local import executor in current stage: {f}")
