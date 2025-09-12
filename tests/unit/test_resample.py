# tests/unit/test_resample.py
# ==============================
# 说明：分钟向上重采样窗口聚合的正确性（开=首、收=尾、高/低=极值、量/额=求和）
# - 人工构造 6 根 60s，重采样到 3 分钟（2 根 1m→1 根 2m 仅示例）验证聚合
# ==============================

import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
import importlib

SH_TZ = timezone(timedelta(hours=8))

def ms(dt):
    return int(dt.timestamp() * 1000)

def test_resample_window_ohlcv():
    """构造窗口内多根分钟，验证聚合结果。"""
    mkt = importlib.import_module("backend.services.market")
    # 人工构造 2025-01-02 10:00:00 ~ 10:05:00 的 1m 数据
    t0 = datetime(2025,1,2,10,0,0,tzinfo=SH_TZ)
    rows = []
    # 3 根：10:00, 10:01, 10:02
    # ohlc 设置：open 依次 10,11,12；close 依次 10.5, 11.5, 12.5；高/低：max/min；成交量：100,200,300；额：10k,20k,30k
    for i,(o,c,h,l,v,a) in enumerate([(10,10.5,11,9.5,100,10000),(11,11.5,12,10.5,200,20000),(12,12.5,13,11.5,300,30000)]):
        ts = ms(t0 + timedelta(minutes=i+1))  # 右端（为对齐演示）
        rows.append((ts,o,h,l,c,v,a))
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume","amount"])
    win_start = rows[0][0] - 1*60*1000  # 方便包含第一根（这里不严格）
    win_end   = rows[-1][0]
    agg = mkt._resample_window(df, win_start, win_end)
    assert agg is not None
    assert agg["o"] == 10.0
    assert agg["c"] == 12.5
    assert agg["h"] == 13.0
    assert agg["l"] == 9.5
    assert agg["v"] == 600.0
    assert agg["a"] == 60000.0
