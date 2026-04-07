# backend/services/market_gap.py
# ==============================
# 行情正式缺口判断模块
#
# 职责：
#   - day 缺口判断
#   - minute 缺口判断
#   - factor 可复用/可计算性判断
#
# 设计原则：
#   - 只做业务级判断
#   - 不做数据拉取
#   - 不做数据写入
#   - BJ 无远程可补时：允许 has_gap=true 但流程可完成
# ==============================

from __future__ import annotations

from typing import Dict, Any
import pandas as pd

from backend.db.calendar import is_trading_day, get_recent_trading_days
from backend.db.factors import get_factors_latest_updated_at
from backend.utils.time import (
    today_ymd,
    now_dt,
    to_yyyymmdd,
    to_yyyymmdd_from_iso,
)
from backend.utils.time_helper import calculate_theoretical_latest_for_frontend


def _is_remote_supported_for_market(market: str) -> bool:
    return str(market or "").strip().upper() in ("SH", "SZ")


def _expected_latest_day_date() -> int:
    """
    日线理论最新日期：
      - 若今天是交易日且已收盘 -> 今天
      - 否则 -> 最近交易日
    """
    today = today_ymd()
    now = now_dt()

    if is_trading_day(today, market="CN"):
        if now.hour > 15 or (now.hour == 15 and now.minute >= 0):
            return today

    recent = get_recent_trading_days(n=1, market="CN")
    if recent:
        return int(recent[0])

    return today


def assess_day_gap(
    *,
    market: str,
    code: str,
    day_df: pd.DataFrame | None,
) -> Dict[str, Any]:
    """
    评估日线是否有缺口。
    """
    m = str(market or "").strip().upper()
    remote_supported = _is_remote_supported_for_market(m)

    if day_df is None or day_df.empty:
        return {
            "has_gap": True,
            "remote_supported": remote_supported,
            "can_continue_remote": remote_supported,
            "local_last_date": None,
            "expected_latest_date": _expected_latest_day_date(),
            "gap_message": (
                "本地暂无日线数据，可尝试远程补齐"
                if remote_supported else
                "本地暂无日线数据，且当前市场无实时远程补齐能力"
            ),
        }

    if "ts" not in day_df.columns:
        raise ValueError("day_df missing ts column")

    local_last_ts = int(day_df["ts"].iloc[-1])
    local_last_date = to_yyyymmdd(local_last_ts)
    expected_latest_date = _expected_latest_day_date()

    has_gap = int(local_last_date) < int(expected_latest_date)

    if not has_gap:
        return {
            "has_gap": False,
            "remote_supported": remote_supported,
            "can_continue_remote": False,
            "local_last_date": local_last_date,
            "expected_latest_date": expected_latest_date,
            "gap_message": "",
        }

    return {
        "has_gap": True,
        "remote_supported": remote_supported,
        "can_continue_remote": remote_supported,
        "local_last_date": local_last_date,
        "expected_latest_date": expected_latest_date,
        "gap_message": (
            f"日线存在缺口：本地最新={local_last_date}，理论最新={expected_latest_date}"
            if remote_supported else
            f"日线存在缺口：本地最新={local_last_date}，理论最新={expected_latest_date}；"
            f"当前市场无实时远程补齐能力，仅返回本地已有数据"
        ),
    }


def _expected_latest_minute_key(*, freq: str) -> tuple[int, str]:
    """
    用前端理论最新时间戳推导 minute 最新桶。
    """
    ts = calculate_theoretical_latest_for_frontend(freq)
    ymd = to_yyyymmdd(ts)
    dt = now_dt()

    if freq == "1m":
        time_text = f"{dt.hour:02d}:{dt.minute:02d}"
    else:
        minute = (dt.minute // 5) * 5
        time_text = f"{dt.hour:02d}:{minute:02d}"

    return ymd, time_text


def assess_minute_gap(
    *,
    market: str,
    code: str,
    freq: str,
    minute_df: pd.DataFrame | None,
) -> Dict[str, Any]:
    """
    评估 1m / 5m 是否有缺口。
    """
    f = str(freq or "").strip()
    if f not in ("1m", "5m"):
        raise ValueError(f"unsupported minute gap freq: {freq}")

    m = str(market or "").strip().upper()
    remote_supported = _is_remote_supported_for_market(m)
    expected_latest_key = _expected_latest_minute_key(freq=f)

    if minute_df is None or minute_df.empty:
        return {
            "has_gap": True,
            "remote_supported": remote_supported,
            "can_continue_remote": remote_supported,
            "local_last_key": None,
            "expected_latest_key": expected_latest_key,
            "gap_message": (
                f"本地暂无 {f} 数据，可尝试远程补齐"
                if remote_supported else
                f"本地暂无 {f} 数据，且当前市场无实时远程补齐能力"
            ),
        }

    required = {"date", "time"}
    if not required.issubset(set(minute_df.columns)):
        raise ValueError(f"minute_df missing columns: {sorted(required - set(minute_df.columns))}")

    local_last_date = int(minute_df["date"].iloc[-1])
    local_last_time = str(minute_df["time"].iloc[-1]).strip()
    local_last_key = (local_last_date, local_last_time)

    has_gap = local_last_key < expected_latest_key

    if not has_gap:
        return {
            "has_gap": False,
            "remote_supported": remote_supported,
            "can_continue_remote": False,
            "local_last_key": local_last_key,
            "expected_latest_key": expected_latest_key,
            "gap_message": "",
        }

    return {
        "has_gap": True,
        "remote_supported": remote_supported,
        "can_continue_remote": remote_supported,
        "local_last_key": local_last_key,
        "expected_latest_key": expected_latest_key,
        "gap_message": (
            f"{f} 数据存在缺口：本地最新={local_last_date} {local_last_time}，"
            f"理论最新={expected_latest_key[0]} {expected_latest_key[1]}"
            if remote_supported else
            f"{f} 数据存在缺口：本地最新={local_last_date} {local_last_time}，"
            f"理论最新={expected_latest_key[0]} {expected_latest_key[1]}；"
            f"当前市场无实时远程补齐能力，仅返回本地已有数据"
        ),
    }


def assess_factor_state(
    *,
    market: str,
    code: str,
    day_df: pd.DataFrame | None,
    request_adjust: str,
) -> Dict[str, Any]:
    """
    评估 factor 是否：
      - 已可复用
      - 可重新计算
      - 不可用（但不阻断）
    """
    req_adj = str(request_adjust or "none").strip().lower()
    if req_adj not in ("none", "qfq", "hfq"):
        req_adj = "none"

    if req_adj == "none":
        return {
            "factor_ready": False,
            "factor_complete": False,
            "can_compute": False,
            "message": "",
        }

    updated_at = get_factors_latest_updated_at(code)
    if updated_at:
        try:
            if int(to_yyyymmdd_from_iso(updated_at)) == int(today_ymd()):
                return {
                    "factor_ready": True,
                    "factor_complete": True,
                    "can_compute": True,
                    "message": "",
                }
        except Exception:
            pass

    can_compute = day_df is not None and not day_df.empty
    return {
        "factor_ready": False,
        "factor_complete": False,
        "can_compute": bool(can_compute),
        "message": (
            "复权因子尚未就绪，可尝试按本地日线重新计算"
            if can_compute else
            "复权因子不可用：当前本地日线不足，后续将安全降级返回不复权数据"
        ),
    }
