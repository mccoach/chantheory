# backend/utils/gap_checker.py
# ==============================
# 缺口判断器（V6.1 - K线按 adjust 维度判断）
# 改动：
#   - check_kline_gap_to_current 增加 adjust 维度：
#       * 默认 adjust='none'
#       * 通过 get_latest_ts_from_raw(symbol, freq, adjust) 判断缺口
#   - 其他逻辑保持不变（后续会在指令集接入后进一步区分 stock/fund 的判断规则）
# ==============================

from __future__ import annotations

from typing import Optional

from backend.db.candles import get_latest_ts_from_raw
from backend.db.symbols import get_profile_updated_at
from backend.db.factors import get_factors_latest_updated_at
from backend.db.calendar import get_latest_date
from backend.db.connection import get_conn
from backend.utils.time_helper import calculate_theoretical_latest_for_frontend
from backend.utils.time import today_ymd, to_yyyymmdd_from_iso
from backend.utils.logger import get_logger

_LOG = get_logger("gap_checker")


def check_calendar_gap(**kwargs) -> bool:
    """
    交易日历缺口判断

    规则：
      - 本地最晚日期 >= 今日 → 无缺口（跳过）
      - 本地最晚日期 < 今日 → 有缺口（拉新）
      - 本地无数据 → 有缺口
    """
    local_latest = get_latest_date()
    today = today_ymd()

    if local_latest is None:
        _LOG.debug("[缺口] 交易日历无数据 → 有缺口")
        return True

    has_gap = local_latest < today

    _LOG.debug(
        f"[缺口] 交易日历 本地最晚={local_latest} 今日={today} "
        f"→ {'有缺口' if has_gap else '无缺口'}"
    )

    return has_gap


def check_kline_gap_to_current(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    adjust: str = "none",
    **kwargs,
) -> bool:
    """
    K线缺口判断（支持 adjust 和强制拉取）

    当前规则（基础版）：
      - 若 force_fetch=True → 直接认为有缺口；
      - 否则：
          * 读取本地 candles_raw 中 (symbol,freq,adjust) 的 MAX(ts)；
          * 与 theoretical_latest_for_frontend(freq) 对比：
              - 本地 < 理论 → 有缺口；
              - 否则无缺口。

    后续扩展：
      - 按 class 区分 stock/fund，fund 对复权数据的缺口判断会更精细；
      - 此处接口已预留 adjust/class 等维度。
    """

    # ===== 强制拉取：绕过判断 =====
    if force_fetch:
        _LOG.debug(
            f"[缺口] {symbol} {freq} adjust={adjust} 强制拉取模式 → 有缺口"
        )
        return True

    # ===== 正常判断 =====
    local_latest_ts = get_latest_ts_from_raw(symbol, freq, adjust=adjust)

    if local_latest_ts is None:
        _LOG.debug(
            f"[缺口] {symbol} {freq} adjust={adjust} 本地无数据 → 有缺口"
        )
        return True

    theoretical_ts = calculate_theoretical_latest_for_frontend(freq)
    has_gap = local_latest_ts < theoretical_ts

    _LOG.debug(
        f"[缺口] {symbol} {freq} adjust={adjust} "
        f"本地={local_latest_ts} 理论={theoretical_ts} "
        f"→ {'有缺口' if has_gap else '无缺口'}"
    )

    return has_gap


def check_info_updated_today(symbol: str, data_type_id: str, **kwargs) -> bool:
    """信息缺口判断（是否今日已更新）"""
    today = today_ymd()

    if "profile" in data_type_id:
        updated_at = get_profile_updated_at(symbol)

        if not updated_at:
            _LOG.debug(f"[缺口] {symbol} 档案不存在 → 有缺口")
            return True

        try:
            updated_ymd = to_yyyymmdd_from_iso(updated_at)
        except Exception:
            _LOG.debug(f"[缺口] {symbol} 档案时间解析失败 → 有缺口")
            return True

        has_gap = updated_ymd < today

        _LOG.debug(
            f"[缺口] {symbol} 档案 "
            f"更新日期={updated_ymd} 今日={today} "
            f"→ {'有缺口' if has_gap else '无缺口'}"
        )

        return has_gap

    elif "factors" in data_type_id:
        updated_at = get_factors_latest_updated_at(symbol)

        if not updated_at:
            _LOG.debug(f"[缺口] {symbol} 因子不存在 → 有缺口")
            return True

        try:
            updated_ymd = to_yyyymmdd_from_iso(updated_at)
        except Exception:
            _LOG.debug(f"[缺口] {symbol} 因子时间解析失败 → 有缺口")
            return True

        has_gap = updated_ymd < today

        _LOG.debug(
            f"[缺口] {symbol} 因子 "
            f"更新日期={updated_ymd} 今日={today} "
            f"→ {'有缺口' if has_gap else '无缺口'}"
        )

        return has_gap

    else:
        _LOG.warning(f"[缺口] 未知数据类型 {data_type_id}")
        return True


# ===== 标的列表缺口判断（保持现有逻辑）=====
def check_symbol_index_gap(force_fetch: bool = False, **kwargs) -> bool:
    """
    标的列表缺口判断（简洁版）

    规则：
      - 若 force_fetch=True → 直接判定有缺口（无条件刷新）
      - 否则：
          * 查询 MAX(updated_at)
          * 提取日期部分（YYYYMMDD）
          * 如果 = 今日 → 无缺口（跳过拉取）
          * 如果 < 今日 → 有缺口（拉新）
          * 如果无数据/解析失败 → 有缺口
    """
    if force_fetch:
        _LOG.debug("[缺口] 标的列表强制刷新模式 → 有缺口")
        return True

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT MAX(updated_at) FROM symbol_index;")
    result = cur.fetchone()

    if not result or not result[0]:
        _LOG.debug("[缺口] 标的列表无数据 → 有缺口")
        return True

    try:
        updated_at = result[0]
        updated_ymd = to_yyyymmdd_from_iso(updated_at)
    except Exception as e:
        _LOG.debug(f"[缺口] 标的列表时间解析失败 → 有缺口, error={e}")
        return True

    today = today_ymd()
    has_gap = updated_ymd < today

    _LOG.debug(
        f"[缺口] 标的列表 "
        f"更新日期={updated_ymd} 今日={today} "
        f"→ {'有缺口' if has_gap else '无缺口'}"
    )

    return has_gap