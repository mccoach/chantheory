# backend/services/indicators.py
# ==============================
# 说明：技术指标计算（纯函数、无副作用、根因重构版）
# - 输入：pandas Series（或 DataFrame 列），输出：dict[str, Series]
# - 指标：MA / MACD / KDJ / RSI / BOLL
# - 约定：输入 close/high/low 均为 float 序列，长度可变
# - 核心重构 (ma 函数):
#   - 签名改为接收一个“key 到周期”的字典，例如 `{'MA5': 12, 'MA10': 21}`。
#   - 返回的字典，其键名严格使用传入的 key（如 'MA5', 'MA10'），而不再根据周期动态生成，
#     保证 key 的绝对固定，彻底解决前端非标 MA 周期显示问题。
# ==============================

from __future__ import annotations  # 引入 Python 3.7+ 的注解前置功能，便于类型提示
import pandas as pd              # 引入 pandas，用于序列化计算和数据处理
import numpy as np               # 引入 numpy，用于数值计算（虽然本文件未直接使用，但 pandas 依赖它）

def ma(close: pd.Series, periods_map: dict[str, int]) -> dict[str, pd.Series]:
    """
    计算多条简单移动平均（SMA）。
    - close: 收盘价的 pandas Series。
    - periods_map: 一个字典，键是固定的 series key (如 'MA5'), 值是周期 (如 12)。
    - 返回: 一个字典，键是固定的 key，值是计算出的 MA 序列。
    """
    out: dict[str, pd.Series] = {}                   # 初始化一个空字典，用于存放结果
    if not isinstance(periods_map, dict):            # 防御性编程：如果传入的不是字典，直接返回空
        return out

    # 遍历传入的“key 到周期”映射
    for key, period in periods_map.items():
        try:
            n = int(period)                          # 尝试将周期转换为整数
            if n > 0:                                # 确保周期是正数
                # 核心修复：使用传入的、固定的 key 作为输出字典的键
                # `close.rolling(n, min_periods=1).mean()` 计算滑动平均
                # `min_periods=1` 确保序列头部不足一个周期时也能计算（从第一个点开始）
                out[key] = close.rolling(n, min_periods=1).mean()
        except (ValueError, TypeError):              # 捕获周期无法转为整数的异常
            continue                                 # 忽略无效的周期值，继续下一个

    return out                                       # 返回计算结果字典

def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, pd.Series]:
    """
    计算 MACD 指标（DIF, DEA, HIST）。
    - close: 收盘价的 pandas Series。
    - fast, slow, signal: MACD 的标准参数。
    """
    # 计算快线 EMA（指数移动平均）
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    # 计算慢线 EMA
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    # 计算 DIF（差离值）
    dif = ema_fast - ema_slow
    # 计算 DEA（信号线）
    dea = dif.ewm(span=signal, adjust=False).mean()
    # 计算 HIST（柱状图），通常乘以 2 以增强视觉效果
    hist = (dif - dea) * 2
    # 返回包含三条线的字典
    return {"MACD_DIF": dif, "MACD_DEA": dea, "MACD_HIST": hist}

def kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9, k: int = 3, d: int = 3) -> dict[str, pd.Series]:
    """
    计算 KDJ 指标。
    - high, low, close: 最高价、最低价、收盘价的 pandas Series。
    - n, k, d: KDJ 的标准参数。
    """
    # 计算最近 n 周期的最低价
    ll = low.rolling(n, min_periods=1).min()
    # 计算最近 n 周期内的最高价
    hh = high.rolling(n, min_periods=1).max()
    # 计算 RSV（未成熟随机值），加上一个极小值 1e-12 避免分母为零
    rsv = (close - ll) / (hh - ll + 1e-12) * 100
    # 计算 K 值（RSV 的加权移动平均）
    k_val = rsv.ewm(alpha=1 / k, adjust=False).mean()
    # 计算 D 值（K 值的加权移动平均）
    d_val = k_val.ewm(alpha=1 / d, adjust=False).mean()
    # 计算 J 值
    j_val = 3 * k_val - 2 * d_val
    # 返回包含三条线的字典
    return {"KDJ_K": k_val, "KDJ_D": d_val, "KDJ_J": j_val}

def rsi(close: pd.Series, n: int = 14) -> dict[str, pd.Series]:
    """
    计算 RSI 指标（相对强弱指数）。
    - close: 收盘价的 pandas Series。
    - n: RSI 的周期参数。
    """
    # 计算每日价格变化
    delta = close.diff()
    # 分离上涨和下跌
    up = delta.clip(lower=0)    # 所有负值变为 0
    down = -delta.clip(upper=0) # 所有正值变为 0，然后取反
    # 计算上涨和下跌的指数移动平均
    roll_up = up.ewm(alpha=1 / n, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / n, adjust=False).mean()
    # 计算相对强度（RS），加上极小值避免分母为零
    rs = roll_up / (roll_down + 1e-12)
    # 计算 RSI
    rsi_val = 100 - (100 / (1 + rs))
    # 返回包含 RSI 线的字典
    return {"RSI": rsi_val}

def boll(close: pd.Series, n: int = 20, k: float = 2.0) -> dict[str, pd.Series]:
    """
    计算布林带（BOLL）。
    - close: 收盘价的 pandas Series。
    - n: 周期参数。
    - k: 标准差倍数。
    """
    # 计算中轨（n 周期的简单移动平均）
    mid = close.rolling(n, min_periods=1).mean()
    # 计算标准差，ddof=0 表示使用总体标准差
    std = close.rolling(n, min_periods=1).std(ddof=0)
    # 计算上轨
    upper = mid + k * std
    # 计算下轨
    lower = mid - k * std
    # 返回包含三条线的字典
    return {"BOLL_MID": mid, "BOLL_UPPER": upper, "BOLL_LOWER": lower}
