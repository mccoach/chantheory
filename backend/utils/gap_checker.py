# backend/utils/gap_checker.py
# ==============================
# 缺口判断器（V8.0）
#
# 改动：
#   - trade_calendar 已改为“触发即执行”的本地完整自然日历构建，
#     不再参与任何缺口判断
#   - profile_snapshot 已改为批量快照导入，不再走缺口判断
#   - 日线真相源已切为 candles_day_raw：
#       (market, symbol, ts)
#   - 当前阶段仅对 1d 缺口判断提供稳定支持
#   - 分钟线后续将切换为归档读取链路
# ==============================

from __future__ import annotations

from backend.db.candles import get_latest_ts_from_day_raw
from backend.db.factors import get_factors_latest_updated_at
from backend.utils.time_helper import calculate_theoretical_latest_for_frontend
from backend.utils.time import today_ymd, to_yyyymmdd_from_iso
from backend.utils.common import get_symbol_market_from_db
from backend.utils.logger import get_logger

_LOG = get_logger("gap_checker")


def check_kline_gap_to_current(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    market: str | None = None,
    **kwargs,
) -> bool:
    """
    K线缺口判断（当前阶段：仅日线稳定支持）

    规则：
      - 若 force_fetch=True → 直接认为有缺口；
      - 若 freq!='1d' → 当前阶段统一认为有缺口（交由上层按后续分钟线归档方案处理）；
      - 否则：
          * 读取本地 candles_day_raw 中 (market,symbol) 的 MAX(ts)；
          * 与 theoretical_latest_for_frontend('1d') 对比：
              - 本地 < 理论 → 有缺口；
              - 否则无缺口。
    """
    if force_fetch:
        _LOG.debug(
            f"[缺口] {market or '?'} {symbol} {freq} 强制拉取模式 → 有缺口"
        )
        return True

    freq_norm = str(freq or "").strip()
    if freq_norm != "1d":
        _LOG.debug(f"[缺口] {symbol} {freq_norm} 当前阶段非日线统一视为有缺口")
        return True

    market_u = str(market or "").strip().upper()
    if not market_u:
        market_u = get_symbol_market_from_db(symbol) or ""

    if not market_u:
        _LOG.debug(f"[缺口] {symbol} {freq_norm} 无法确定 market → 有缺口")
        return True

    local_latest_ts = get_latest_ts_from_day_raw(market=market_u, symbol=symbol)

    if local_latest_ts is None:
        _LOG.debug(
            f"[缺口] {market_u} {symbol} {freq_norm} 本地无数据 → 有缺口"
        )
        return True

    theoretical_ts = calculate_theoretical_latest_for_frontend(freq_norm)
    has_gap = local_latest_ts < theoretical_ts

    _LOG.debug(
        f"[缺口] {market_u} {symbol} {freq_norm} "
        f"本地={local_latest_ts} 理论={theoretical_ts} "
        f"→ {'有缺口' if has_gap else '无缺口'}"
    )

    return has_gap


def check_info_updated_today(symbol: str, data_type_id: str, **kwargs) -> bool:
    today = today_ymd()

    if "factors" in data_type_id:
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

    _LOG.warning(f"[缺口] 未知或已废弃的数据类型 {data_type_id}")
    return True
