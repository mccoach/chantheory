# backend/datasource/providers/baostock_adapter/factors_bs.py
# ==============================
# 说明：Baostock 复权因子适配器 (V4.0 - 纯原子·一次拉取全部因子)
#
# 职责：
#   - 封装 baostock.query_adjust_factor 调用；
#   - 对外暴露一次性接口 get_raw_adj_factors_bs(symbol, start_date, end_date)：
#       * 返回 Baostock 原始字段，不做业务级处理：
#           - 'code'
#           - 'dividOperateDate'
#           - 'foreAdjustFactor'
#           - 'backAdjustFactor'
#           - 'adjustFactor'
#   - 不解析日期、不改列名、不做拆分/合并，不直接与 DB 发生关系。
#
# 说明：
#   - symbol → 远程代码 的唯一来源是 symbol_index.market，经由
#       backend.utils.common.prefix_symbol_with_market 统一生成，如 'sh.600000'。
#   - 所有“什么是前复权/后复权、如何落库”的逻辑，统一交给 normalizer + services 层。
# ==============================

from __future__ import annotations

import asyncio
from typing import Optional

import pandas as pd

from backend.utils.async_limiter import limit_async_network_io
from backend.utils.logger import get_logger
from backend.utils.common import prefix_symbol_with_market

_LOG = get_logger("baostock_adapter")

# 直接导入 baostock
try:
    import baostock as bs
except ImportError as e:
    raise ImportError(
        "baostock library is required but not installed. "
        "Please install it via: pip install baostock"
    ) from e


async def _run_sync_in_thread(func, *args, **kwargs):
    """在线程池中执行同步阻塞调用。"""
    return await asyncio.to_thread(func, *args, **kwargs)


def _query_adjust_factor_sync(
    code: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    同步调用 baostock.query_adjust_factor，返回原始 DataFrame。

    预期列（以官方文档与示例为准）：
      - 'code'             : 如 'sh.600000'
      - 'dividOperateDate' : 'YYYY-MM-DD'
      - 'foreAdjustFactor' : 前复权因子
      - 'backAdjustFactor' : 后复权因子
      - 'adjustFactor'     : 综合因子（当前未用）
    """
    lg = bs.login()
    if lg.error_code != "0":
        _LOG.error(
            "[Baostock] login failed: %s - %s",
            lg.error_code,
            lg.error_msg,
        )
        bs.logout()
        raise RuntimeError(
            f"baostock login failed: {lg.error_code} - {lg.error_msg}"
        )

    try:
        rs = bs.query_adjust_factor(
            code=code,
            start_date=start_date,
            end_date=end_date,
        )
        if rs.error_code != "0":
            _LOG.error(
                "[Baostock] query_adjust_factor failed: %s - %s",
                rs.error_code,
                rs.error_msg,
            )
            raise RuntimeError(
                f"baostock query_adjust_factor failed: "
                f"{rs.error_code} - {rs.error_msg}"
            )

        rows = []
        while (rs.error_code == "0") & rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            _LOG.warning(
                "[Baostock] query_adjust_factor returned empty: code=%s, "
                "start_date=%s, end_date=%s",
                code,
                start_date,
                end_date,
            )
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=rs.fields)
        _LOG.info(
            "[Baostock] query_adjust_factor raw fetched: code=%s, rows=%d, columns=%s",
            code,
            len(df),
            list(df.columns),
        )
        return df

    finally:
        try:
            bs.logout()
        except Exception:
            pass


@limit_async_network_io
async def get_raw_adj_factors_bs(
    symbol: str,
    start_date: str = "1990-01-01",
    end_date: str = "2100-12-31",
) -> pd.DataFrame:
    """
    [复权因子 · Baostock 原子接口 · 一次拉取全部因子（前/后）]

    参数：
      - symbol: 内部使用的无前缀代码，如 '600000'
      - start_date, end_date: 'YYYY-MM-DD'

    返回：
      - DataFrame，列为 Baostock 原始字段：
          ['code', 'dividOperateDate', 'foreAdjustFactor',
           'backAdjustFactor', 'adjustFactor']
      - 若无数据，则返回空 DataFrame。
    """
    sym = (symbol or "").strip()
    if not sym:
        _LOG.warning("[Baostock] get_raw_adj_factors_bs: empty symbol")
        return pd.DataFrame()

    # 使用 symbol_index.market 统一生成远程代码（如 'sh.600000'）
    remote_code = prefix_symbol_with_market(sym)

    df = await _run_sync_in_thread(
        _query_adjust_factor_sync,
        code=remote_code,
        start_date=start_date,
        end_date=end_date,
    )
    return df if df is not None else pd.DataFrame()