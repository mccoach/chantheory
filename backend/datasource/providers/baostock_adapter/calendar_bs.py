# backend/datasource/providers/baostock_adapter/calendar_bs.py
# ==============================
# 说明：Baostock 交易日历适配器 (V1.1 - 纯原子版)
#
# 职责：
#   - 仅封装对 baostock.query_trade_dates 的调用；
#   - 提供异步函数 get_trade_calendar_bs，返回 pandas.DataFrame；
#   - 不做任何业务级清洗和字段标准化（不重命名、不按 is_trading_day 过滤）。
#
# 设计与约束：
#   - 与 akshare_adapter / sse_adapter / szse_adapter 风格保持一致：
#       * 对外暴露 async 函数；
#       * 内部通过 asyncio.to_thread 执行同步 baostock 调用；
#       * 使用 limit_async_network_io 做全局异步限流。
#   - 返回结构：
#       * 列示例（基于你提供的实际输出）：
#           - 'calendar_date' : 'YYYY-MM-DD' 字符串
#           - 'is_trading_day': '0' 或 '1'
#         以及 baostock 可能附带的其他字段（原样保留）。
#   - 统一的“什么是交易日”判断、以及日期格式转换，放在 normalizer 层处理。
# ==============================

from __future__ import annotations

import asyncio
from typing import Optional

import pandas as pd

from backend.utils.async_limiter import limit_async_network_io
from backend.utils.logger import get_logger

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
    """
    在独立线程中执行同步阻塞函数，并返回其结果。
    作用与 akshare_adapter._run_sync_in_thread 相同，避免阻塞主事件循环。
    """
    return await asyncio.to_thread(func, *args, **kwargs)


@limit_async_network_io
async def get_trade_calendar_bs(
    start_date: str = "1990-01-01",
    end_date: str = "2100-12-31",
) -> pd.DataFrame:
    """
    [交易日历 Baostock 原子接口]

    数据源：
      - baostock API: bs.query_trade_dates(start_date, end_date)

    行为（同步部分在线程池中执行）：
      1) bs.login()
      2) rs = bs.query_trade_dates(start_date, end_date)
      3) 迭代 rs.next() 收集数据 → DataFrame(columns=rs.fields)
      4) bs.logout()

    返回：
      - pandas.DataFrame：
          * 至少包含：
              - 'calendar_date' : 'YYYY-MM-DD' 字符串
              - 'is_trading_day': '0' 或 '1'
          * 以及 baostock 返回的其他字段（若有）一并保留；
      - 不做任何过滤和重命名（保持“原始数据”语义）。
      - 空数据或异常时返回空 DataFrame（异常由上层 dispatcher 分类处理）。
    """

    def _fetch_calendar_sync() -> pd.DataFrame:
        """在同步上下文中调用 baostock 接口（运行在线程池中）"""
        # 1. 登录
        lg = bs.login()
        if lg.error_code != "0":
            # 登录失败，立即退出
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
            # 2. 查询交易日
            rs = bs.query_trade_dates(
                start_date=start_date,
                end_date=end_date,
            )
            if rs.error_code != "0":
                _LOG.error(
                    "[Baostock] query_trade_dates failed: %s - %s",
                    rs.error_code,
                    rs.error_msg,
                )
                raise RuntimeError(
                    f"baostock query_trade_dates failed: "
                    f"{rs.error_code} - {rs.error_msg}"
                )

            # 3. 迭代收集结果
            data_list = []
            while (rs.error_code == "0") & rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                _LOG.warning(
                    "[Baostock] query_trade_dates returned empty result: "
                    "start_date=%s, end_date=%s",
                    start_date,
                    end_date,
                )
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)

            _LOG.info(
                "[Baostock] trade calendar fetched: rows=%d, "
                "start_date=%s, end_date=%s, columns=%s",
                len(df),
                start_date,
                end_date,
                list(df.columns),
            )

            return df

        finally:
            # 4. 确保登出
            try:
                bs.logout()
            except Exception:
                # 登出失败不影响主流程
                pass

    # 在线程池中执行同步函数
    df = await _run_sync_in_thread(_fetch_calendar_sync)

    # 防御性处理：保持返回为 DataFrame
    return df if df is not None else pd.DataFrame()