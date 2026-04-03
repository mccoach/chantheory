# backend/utils/minute_bucket.py
# ==============================
# 中国A股分钟桶规则工具
#
# 职责：
#   - 给定最后一根分钟K线的 (date, time, freq)
#   - 依据中国A股交易时段 + 交易日历
#   - 推算理论上下一根合法分钟桶
#
# 当前支持：
#   - 1m
#   - 5m
#
# 桶结束时刻语义：
#   - 1m:  09:31 ~ 11:30, 13:01 ~ 15:00
#   - 5m:  09:35 ~ 11:30, 13:05 ~ 15:00
# ==============================

from __future__ import annotations

from datetime import datetime, timedelta

from backend.db.calendar import is_trading_day
from backend.utils.time import parse_yyyymmdd, shift_days


def _parse_time_text_to_hm(time_text: str) -> tuple[int, int]:
    s = str(time_text or "").strip()
    if ":" not in s:
        raise ValueError(f"invalid minute bucket time text: {time_text}")
    hh, mm = s.split(":", 1)
    try:
        h = int(hh)
        m = int(mm)
    except Exception:
        raise ValueError(f"invalid minute bucket time text: {time_text}")
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"invalid minute bucket time text: {time_text}")
    return h, m


def _time_text(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _freq_minutes(freq: str) -> int:
    f = str(freq or "").strip()
    if f == "1m":
        return 1
    if f == "5m":
        return 5
    raise ValueError(f"unsupported minute bucket freq: {freq}")


def _session_open_bucket(freq: str) -> str:
    f = str(freq or "").strip()
    if f == "1m":
        return "09:31"
    if f == "5m":
        return "09:35"
    raise ValueError(f"unsupported minute bucket freq: {freq}")


def _afternoon_open_bucket(freq: str) -> str:
    f = str(freq or "").strip()
    if f == "1m":
        return "13:01"
    if f == "5m":
        return "13:05"
    raise ValueError(f"unsupported minute bucket freq: {freq}")


def _next_trading_day(date_ymd: int) -> int:
    d = int(date_ymd)
    for _ in range(1, 370):
        d = shift_days(d, 1)
        if is_trading_day(d, market="CN"):
            return d
    raise ValueError(f"cannot find next trading day after {date_ymd}")


def next_minute_bucket_key(
    *,
    last_date: int,
    last_time: str,
    freq: str,
) -> tuple[int, str]:
    """
    根据最后一根分钟K线推算理论下一根合法分钟桶。

    Args:
        last_date: YYYYMMDD
        last_time: HH:MM
        freq     : 1m / 5m

    Returns:
        (next_date, next_time)
    """
    date_ymd = parse_yyyymmdd(last_date)
    h, m = _parse_time_text_to_hm(last_time)
    step = _freq_minutes(freq)

    # 上午时段内推进
    if (h < 11) or (h == 11 and m < 30):
        dt = datetime(2000, 1, 1, h, m) + timedelta(minutes=step)
        nh, nm = dt.hour, dt.minute

        if nh < 11 or (nh == 11 and nm <= 30):
            return date_ymd, _time_text(nh, nm)

        return date_ymd, _afternoon_open_bucket(freq)

    # 上午收盘桶 -> 下午首桶
    if h == 11 and m == 30:
        return date_ymd, _afternoon_open_bucket(freq)

    # 下午时段推进
    if (h >= 13) and (h < 15 or (h == 15 and m == 0)):
        if h == 15 and m == 0:
            next_day = _next_trading_day(date_ymd)
            return next_day, _session_open_bucket(freq)

        dt = datetime(2000, 1, 1, h, m) + timedelta(minutes=step)
        nh, nm = dt.hour, dt.minute

        if nh < 15 or (nh == 15 and nm == 0):
            return date_ymd, _time_text(nh, nm)

        next_day = _next_trading_day(date_ymd)
        return next_day, _session_open_bucket(freq)

    raise ValueError(
        f"unsupported or invalid last minute bucket: date={date_ymd}, time={last_time}, freq={freq}"
    )
