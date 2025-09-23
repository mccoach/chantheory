# backend/utils/window_preset.py
# ==============================
# 说明：频率 × 窗宽 预设 → bars（根数）查表工具（服务端唯一可信实现）
# - 向上取整，宁多勿少
# - 分钟族按 240 分钟/日近似（1m=240，5m=48，15m=16，30m=8，60m=4）
# - 日线按交易日近似（1M≈22, 3M≈66, 6M≈132, 1Y≈244, 3Y≈732, 5Y≈1220）
# - 周/月线按周/月近似（周：4/12/26/52/156/260；月：1/3/6/12/36/60）
# - ALL 的 bars 等于 total_rows
from __future__ import annotations  # 前置注解（兼容 3.8+）

import math  # 向上取整
from typing import Optional  # 可选类型

# 可选窗宽枚举（与前端一致）
WINDOW_PRESETS = ["5D", "10D", "1M", "3M", "6M", "1Y", "3Y", "5Y", "ALL"]  # 预设键

def _minute_bars_per_day(freq: str) -> int:
    """分钟族：按 240 分钟/日近似换算为“每日根数”"""
    m = {
        "1m": 240,
        "5m": 240 // 5,
        "15m": 240 // 15,
        "30m": 240 // 30,
        "60m": 240 // 60,
    }
    return int(m.get(freq, 240))

def _days_of(preset: str) -> int:
    """窗宽 → 天数近似"""
    return {
        "5D": 5,
        "10D": 10,
        "1M": 22,
        "3M": 66,
        "6M": 132,
        "1Y": 244,
        "3Y": 732,
        "5Y": 1220,
    }.get(preset, 0)

def _weeks_of(preset: str) -> int:
    """窗宽 → 周数近似"""
    return {
        "5D": 1,
        "10D": 2,
        "1M": 4,
        "3M": 12,
        "6M": 26,
        "1Y": 52,
        "3Y": 156,
        "5Y": 260,
    }.get(preset, 0)

def _months_of(preset: str) -> int:
    """窗宽 → 月数近似"""
    return {
        "1M": 1,
        "3M": 3,
        "6M": 6,
        "1Y": 12,
        "3Y": 36,
        "5Y": 60,
        "5D": 1,   # 最小回退为 1 月
        "10D": 1,  # 最小回退为 1 月
    }.get(preset, 0)

def preset_to_bars(freq: str, preset: str, total_rows: int) -> int:
    """
    预设 → bars（向上取整，bars ≤ total_rows；ALL=total_rows）
    - freq: '1m'|'5m'|'15m'|'30m'|'60m'|'1d'|'1w'|'1M'
    - preset: 上面 WINDOW_PRESETS 枚举
    - total_rows: 当前 ALL 根数
    """
    n = max(0, int(total_rows or 0))  # ALL 根数
    if str(preset).upper() == "ALL":
        return n
    f = str(freq).strip()
    p = str(preset).strip().upper()
    bars = 0
    if f.endswith("m"):
        per_day = _minute_bars_per_day(f)
        bars = math.ceil(per_day * _days_of(p))
    elif f == "1d":
        bars = math.ceil(_days_of(p))
    elif f == "1w":
        bars = math.ceil(_weeks_of(p))
    elif f == "1M":
        bars = math.ceil(_months_of(p))
    else:
        bars = math.ceil(_days_of(p))
    bars = max(1, int(bars or 0))
    if n > 0:
        bars = min(bars, n)
    return bars
