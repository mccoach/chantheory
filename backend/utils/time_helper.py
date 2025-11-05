# backend/utils/time_helper.py
# ==============================
# 说明：时间计算辅助（依赖统一的 time.py）
# 职责：
#   1. 判断当前是否交易时段
#   2. 计算理论最新时间戳（前端/后台）
# 核心原则：
#   - 所有底层时间运算调用 time.py 标准函数
#   - 本模块只负责业务逻辑（交易时段判断、理论时间戳计算）
# ==============================

from __future__ import annotations

from datetime import time, timedelta

from backend.settings import settings
from backend.db.calendar import is_trading_day, get_recent_trading_days
from backend.utils.logger import get_logger
from backend.utils.time import (
    get_tz,
    now_dt,
    today_ymd,
    ms_at_market_close,
    ms_at_time,
    shift_days
)

_LOG = get_logger("time_helper")

def is_current_trading_hours() -> bool:
    """
    判断当前是否交易时段（09:30-15:00）
    
    Returns:
        bool: 是否交易时段
    """
    now = now_dt()
    
    # 判断是否交易日
    if not is_trading_day(today_ymd()):
        return False
    
    # 判断时间段（直接硬编码，保持直观）
    t = now.time()
    morning = time(9, 30) <= t <= time(11, 30)
    afternoon = time(13, 0) <= t <= time(15, 0)
    
    return morning or afternoon

def calculate_theoretical_latest_for_frontend(freq: str) -> int:
    """
    计算前端数据的理论最新时间戳（当前时刻理论收盘）
    
    统一语义：返回"理论上最新K线的收盘时刻"
    
    Args:
        freq: 频率（'1m', '5m', '1d'等）
    
    Returns:
        int: 理论最新收盘时刻的毫秒时间戳
    
    Examples:
        # 当前时间：2024-11-05 14:37:00（周二盘中）
        >>> calculate_theoretical_latest_for_frontend('1m')
        xxx  # 2024-11-05 14:37:00
        >>> calculate_theoretical_latest_for_frontend('1d')
        xxx  # 2024-11-05 15:00:00
    """
    now = now_dt()
    today = today_ymd()
    
    if freq.endswith('m'):
        # 分钟族：当前时刻向下取整到周期
        period = int(freq[:-1])
        current_minute = (now.minute // period) * period
        
        return ms_at_time(today, now.hour, current_minute, 0)
    
    elif freq == '1d':
        # 日线：当日收盘
        return ms_at_market_close(today)
    
    elif freq == '1w':
        # 周线：本周五收盘（未到周五则取上周五）
        weekday = now.weekday()  # 0=周一, 4=周五
        
        if weekday == 4 and now.time() >= time(15, 0):
            # 今天是周五且已收盘
            friday = now.date()
        elif weekday < 4:
            # 周一到周四 → 上周五
            days_back = weekday + 3
            friday = now.date() - timedelta(days=days_back)
        else:
            # 周五未收盘 或 周六周日 → 上周五
            days_back = weekday - 4 + 7 if weekday > 4 else 0
            friday = now.date() - timedelta(days=days_back) if days_back > 0 else now.date()
        
        friday_ymd = friday.year * 10000 + friday.month * 100 + friday.day
        return ms_at_market_close(friday_ymd)
    
    elif freq == '1M':
        # 月线：本月最后一天（简化）
        next_month_first = now.replace(day=1) + timedelta(days=32)
        last_day = next_month_first.replace(day=1) - timedelta(days=1)
        last_day_ymd = last_day.year * 10000 + last_day.month * 100 + last_day.day
        
        return ms_at_market_close(last_day_ymd)
    
    else:
        # 未知频率，返回当前时间
        return int(now.timestamp() * 1000)

def calculate_theoretical_latest_for_backend(freq: str) -> int:
    """
    计算后台数据的理论最新时间戳（前一交易日收盘）
    
    统一语义：返回"前一交易日的收盘时刻"（15:00）
    
    Args:
        freq: 频率
    
    Returns:
        int: 前一交易日15:00的毫秒时间戳
    """
    # 获取最近交易日
    recent = get_recent_trading_days(n=1)
    
    if not recent:
        # 容错：昨日
        last_trade_ymd = shift_days(today_ymd(), -1)
    else:
        last_trade_ymd = recent[0]
    
    # 统一返回收盘时刻
    return ms_at_market_close(last_trade_ymd)
