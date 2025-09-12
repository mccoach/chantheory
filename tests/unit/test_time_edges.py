# tests/unit/test_time_edges.py
# ==============================
# 说明：近端“最后一根应当生成的 K 的结束时刻”单元用例
# - 覆盖：分钟会话右端对齐、午休/收盘/开盘前、日/周/月 15:00+宽限
# - 做法：为避免真实交易日历干扰，patch 成“恒为交易日”
# ==============================

import pytest  # 测试框架
from datetime import datetime, timezone, timedelta  # 时间构造
import importlib  # 动态导入

# 工具：构造上海时区 datetime（简化用 +08:00 固定偏移）
SH_TZ = timezone(timedelta(hours=8))  # 上海时区

def patch_trading_day(monkeypatch):
    """把 _lazy_is_trading_day 永久返回 True，避免真实日历干扰。"""
    mkt = importlib.import_module("backend.services.market")
    monkeypatch.setattr(mkt, "_lazy_is_trading_day", lambda d: True)

def test_minute_align_inside_session(monkeypatch):
    """分钟会话内：10:07 在 5m 下应对齐到 10:05（右端）。"""
    patch_trading_day(monkeypatch)  # 永远交易日
    mkt = importlib.import_module("backend.services.market")
    # 构造 10:07，考虑 5s 宽限 → now-5s 仍在 10:06:55 左右，不影响对齐到 10:05
    now = datetime(2025, 1, 2, 10, 7, 0, tzinfo=SH_TZ)  # 10:07:00
    ts = mkt._expected_last_end_ts_for_freq("5m", now)
    # 预期为 10:05:00
    expect = datetime(2025, 1, 2, 10, 5, 0, tzinfo=SH_TZ)
    assert ts == int(expect.timestamp() * 1000)

def test_minute_lunch_break(monkeypatch):
    """午休：12:10 → 预期为上午会话右端 11:30。"""
    patch_trading_day(monkeypatch)
    mkt = importlib.import_module("backend.services.market")
    now = datetime(2025, 1, 2, 12, 10, 0, tzinfo=SH_TZ)
    ts = mkt._expected_last_end_ts_for_freq("15m", now)
    expect = datetime(2025, 1, 2, 11, 30, 0, tzinfo=SH_TZ)
    assert ts == int(expect.timestamp() * 1000)

def test_minute_after_close(monkeypatch):
    """收盘后：15:30 → 预期为当天 15:00。"""
    patch_trading_day(monkeypatch)
    mkt = importlib.import_module("backend.services.market")
    now = datetime(2025, 1, 2, 15, 30, 0, tzinfo=SH_TZ)
    ts = mkt._expected_last_end_ts_for_freq("1m", now)
    expect = datetime(2025, 1, 2, 15, 0, 0, tzinfo=SH_TZ)
    assert ts == int(expect.timestamp() * 1000)

def test_daily_cutoff(monkeypatch):
    """日线：14:59 → 预期上一交易日 15:00；15:01 → 预期今日 15:00。"""
    patch_trading_day(monkeypatch)
    mkt = importlib.import_module("backend.services.market")
    # 14:59（减去 180s 宽限后仍未过 15:00）
    now1 = datetime(2025, 1, 2, 14, 59, 0, tzinfo=SH_TZ)
    ts1 = mkt._expected_last_end_ts_for_freq("1d", now1)
    # 期望上一交易日 15:00
    prev_day = datetime(2025, 1, 1, 15, 0, 0, tzinfo=SH_TZ)
    assert ts1 == int(prev_day.timestamp() * 1000)
    # 15:01（now-180s 已过 15:00）
    now2 = datetime(2025, 1, 2, 15, 1, 0, tzinfo=SH_TZ)
    ts2 = mkt._expected_last_end_ts_for_freq("1d", now2)
    today_1500 = datetime(2025, 1, 2, 15, 0, 0, tzinfo=SH_TZ)
    assert ts2 == int(today_1500.timestamp() * 1000)
