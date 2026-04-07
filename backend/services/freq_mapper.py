# backend/services/freq_mapper.py
# ==============================
# 请求频率 -> 后端基础依赖映射
#
# 职责：
#   - 统一定义前端请求频率与后端基础真相源依赖关系
#   - 明确：
#       * 是否需要 1d
#       * 是否需要 minute
#       * minute 需要 1m 还是 5m
#       * 是否需要重采样
#       * 最终结果频率
#
# 设计原则：
#   - 单一职责
#   - 不做缺口判断
#   - 不做数据读取
#   - 不做复权
# ==============================

from __future__ import annotations

from typing import Dict, Any

_ALLOWED_FREQS = {"1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M"}


def map_request_freq(freq: str) -> Dict[str, Any]:
    """
    将前端请求频率映射为后端基础依赖。

    Returns:
        {
          "request_freq": "30m",
          "need_day": True,
          "need_factor": True,
          "need_minute": True,
          "base_minute_freq": "5m",
          "need_resample": True,
          "result_freq": "30m",
        }
    """
    f = str(freq or "").strip()
    if f not in _ALLOWED_FREQS:
        raise ValueError(f"unsupported freq: {freq}")

    if f == "1m":
        return {
            "request_freq": f,
            "need_day": True,
            "need_factor": True,
            "need_minute": True,
            "base_minute_freq": "1m",
            "need_resample": False,
            "result_freq": "1m",
        }

    if f == "5m":
        return {
            "request_freq": f,
            "need_day": True,
            "need_factor": True,
            "need_minute": True,
            "base_minute_freq": "5m",
            "need_resample": False,
            "result_freq": "5m",
        }

    if f in ("15m", "30m", "60m"):
        return {
            "request_freq": f,
            "need_day": True,
            "need_factor": True,
            "need_minute": True,
            "base_minute_freq": "5m",
            "need_resample": True,
            "result_freq": f,
        }

    if f == "1d":
        return {
            "request_freq": f,
            "need_day": True,
            "need_factor": True,
            "need_minute": False,
            "base_minute_freq": None,
            "need_resample": False,
            "result_freq": "1d",
        }

    if f in ("1w", "1M"):
        return {
            "request_freq": f,
            "need_day": True,
            "need_factor": True,
            "need_minute": False,
            "base_minute_freq": None,
            "need_resample": True,
            "result_freq": f,
        }

    raise ValueError(f"unsupported freq: {freq}")
