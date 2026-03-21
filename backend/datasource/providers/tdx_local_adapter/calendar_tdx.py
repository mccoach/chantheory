# backend/datasource/providers/tdx_local_adapter/calendar_tdx.py
# ==============================
# 通达信本地文件适配器 - trade_calendar
#
# 职责：
#   1. 调用本地文件解析层：
#       - needini.dat（节假日休市日）
#   2. 在 provider 层完成“完整自然日历原始表”的组装：
#       - 起点固定：19901219
#       - 终点固定：needini.dat 中最晚年份的 1231
#       - 周六/周日 = 非交易日
#       - needini.dat 节假日 = 非交易日
#   3. 返回统一原始 DataFrame
#
# 输出字段：
#   - date
#   - market
#   - is_trading_day
#
# 明确不做：
#   - 不写 DB
#   - 不发 SSE
#   - 不做业务层跳过判断
# ==============================

from __future__ import annotations

import asyncio
from datetime import timedelta

import pandas as pd

from backend.datasource.local_files import (
    load_needini_holidays_df,
    get_needini_latest_year,
)
from backend.utils.logger import get_logger
from backend.utils.time import to_date_object

_LOG = get_logger("tdx_local_adapter.calendar")

_CALENDAR_START_YMD = 19901219


def _build_trade_calendar_df_sync() -> pd.DataFrame:
    latest_year = int(get_needini_latest_year())
    end_ymd = latest_year * 10000 + 1231

    start_date = to_date_object(_CALENDAR_START_YMD)
    end_date = to_date_object(end_ymd)

    if start_date > end_date:
        raise ValueError(
            f"invalid trade_calendar range: start={_CALENDAR_START_YMD}, end={end_ymd}"
        )

    df_holidays = load_needini_holidays_df()
    holiday_set = set()

    if df_holidays is not None and not df_holidays.empty:
        holiday_set = {
            int(v) for v in df_holidays["date"].tolist()
            if v is not None
        }

    rows = []
    current = start_date

    while current <= end_date:
        ymd = current.year * 10000 + current.month * 100 + current.day
        weekday = current.weekday()  # 0=Mon, 5=Sat, 6=Sun

        is_weekend = weekday >= 5
        is_holiday = ymd in holiday_set

        is_trading_day = 0 if (is_weekend or is_holiday) else 1

        rows.append({
            "date": ymd,
            "market": "CN",
            "is_trading_day": is_trading_day,
        })

        current += timedelta(days=1)

    if not rows:
        return pd.DataFrame(columns=["date", "market", "is_trading_day"])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)

    _LOG.info(
        "[TDX][TRADE_CALENDAR] built rows=%s start=%s end=%s latest_year=%s",
        len(df),
        _CALENDAR_START_YMD,
        end_ymd,
        latest_year,
    )
    return df


async def get_trade_calendar_tdx() -> pd.DataFrame:
    return await asyncio.to_thread(_build_trade_calendar_df_sync)
