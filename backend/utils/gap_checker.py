# backend/utils/gap_checker.py
# ==============================
# 说明：缺口判断器（V4.0 - 使用统一时间标准）
# ==============================

from __future__ import annotations

from typing import Optional

from backend.db.candles import get_latest_ts_from_raw
from backend.db.symbols import select_symbol_profile, get_profile_updated_at
from backend.db.factors import get_latest_factor_date, get_factors_latest_updated_at
from backend.utils.time_helper import (
    calculate_theoretical_latest_for_frontend,
    calculate_theoretical_latest_for_backend
)
from backend.utils.time import today_ymd, to_yyyymmdd_from_iso
from backend.utils.logger import get_logger

_LOG = get_logger("gap_checker")

def check_kline_gap_to_current(symbol: str, freq: str, **kwargs) -> bool:
    """K线缺口判断（到当前时刻）- 用于前端数据"""
    local_latest_ts = get_latest_ts_from_raw(symbol, freq)
    
    if local_latest_ts is None:
        _LOG.debug(f"[缺口判断] {symbol} {freq} 本地无数据 → 有缺口")
        return True
    
    theoretical_ts = calculate_theoretical_latest_for_frontend(freq)
    has_gap = local_latest_ts < theoretical_ts
    
    _LOG.debug(
        f"[缺口判断] {symbol} {freq} "
        f"本地={local_latest_ts} 理论={theoretical_ts} "
        f"→ {'有缺口' if has_gap else '无缺口'}"
    )
    
    return has_gap

def check_kline_gap_to_last_close(symbol: str, freq: str, **kwargs) -> bool:
    """K线缺口判断（到前一交易日收盘）- 用于后台数据"""
    local_latest_ts = get_latest_ts_from_raw(symbol, freq)
    
    if local_latest_ts is None:
        _LOG.debug(f"[缺口判断] {symbol} {freq} 本地无数据 → 有缺口")
        return True
    
    theoretical_ts = calculate_theoretical_latest_for_backend(freq)
    has_gap = local_latest_ts < theoretical_ts
    
    _LOG.debug(
        f"[缺口判断] {symbol} {freq} "
        f"本地={local_latest_ts} 理论={theoretical_ts} "
        f"→ {'有缺口' if has_gap else '无缺口'}"
    )
    
    return has_gap

def check_info_updated_today(symbol: str, data_type_id: str, **kwargs) -> bool:
    """信息缺口判断（是否今日已更新）- 用于档案/因子"""
    today = today_ymd()
    
    if 'profile' in data_type_id:
        updated_at = get_profile_updated_at(symbol)
        
        if not updated_at:
            _LOG.debug(f"[缺口判断] {symbol} 档案不存在 → 有缺口")
            return True
        
        try:
            updated_ymd = to_yyyymmdd_from_iso(updated_at)
        except Exception:
            _LOG.debug(f"[缺口判断] {symbol} 档案updated_at解析失败 → 有缺口")
            return True
        
        has_gap = updated_ymd < today
        
        _LOG.debug(
            f"[缺口判断] {symbol} 档案 "
            f"更新日期={updated_ymd} 今日={today} "
            f"→ {'有缺口' if has_gap else '无缺口'}"
        )
        
        return has_gap
    
    elif 'factors' in data_type_id:
        updated_at = get_factors_latest_updated_at(symbol)
        
        if not updated_at:
            _LOG.debug(f"[缺口判断] {symbol} 因子不存在 → 有缺口")
            return True
        
        try:
            updated_ymd = to_yyyymmdd_from_iso(updated_at)
        except Exception:
            _LOG.debug(f"[缺口判断] {symbol} 因子updated_at解析失败 → 有缺口")
            return True
        
        has_gap = updated_ymd < today
        
        _LOG.debug(
            f"[缺口判断] {symbol} 因子 "
            f"更新日期={updated_ymd} 今日={today} "
            f"→ {'有缺口' if has_gap else '无缺口'}"
        )
        
        return has_gap
    
    else:
        _LOG.warning(f"[缺口判断] 未知数据类型 {data_type_id}")
        return True

def check_record_not_exists(symbol: str, data_type_id: str, **kwargs) -> bool:
    """记录缺口判断（是否存在）- 用于全量档案补缺"""
    if 'profile' in data_type_id:
        exists = select_symbol_profile(symbol) is not None
        
        _LOG.debug(
            f"[缺口判断] {symbol} 档案 "
            f"{'已存在' if exists else '不存在'} "
            f"→ {'无缺口' if exists else '有缺口'}"
        )
        
        return not exists
    
    elif 'factors' in data_type_id:
        exists = get_latest_factor_date(symbol) is not None
        
        _LOG.debug(
            f"[缺口判断] {symbol} 因子 "
            f"{'已存在' if exists else '不存在'} "
            f"→ {'无缺口' if exists else '有缺口'}"
        )
        
        return not exists
    
    else:
        _LOG.warning(f"[缺口判断] 未知数据类型 {data_type_id}")
        return True
