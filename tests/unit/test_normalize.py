# tests/unit/test_normalize.py
# ==============================
# 说明：分钟/日线归一化函数的健壮性测试
# - 本轮变更：放宽分钟归一化列断言，接受实现可能返回的 turnover_rate 列；
#   核心断言为“至少包含关键列 + amount 缺失时为 NA”，避免测试对实现施加错误约束。
# ==============================

import pytest
import pandas as pd
import importlib

def test_norm_minute_df_cn_en_columns():
    """分钟归一化：中英混合列名也能正确归一化。"""
    f = importlib.import_module("backend.datasource.fetchers")  # 导入统一归一化实现
    # 构造含中英混合列名的 DataFrame，且不提供 amount 列
    df = pd.DataFrame({
        "时间": ["2025-01-02 10:00:00", "2025-01-02 10:01:00"],
        "open": [10,11],
        "最高": [11,12],
        "low":  [9.5,10.5],
        "收盘": [10.5,11.5],
        "成交量": [100,200],
        # 成交额缺失：应生成 amount 列为 NA
    })
    y = f._norm_minute_df(df)  # 调用归一化
    # 断言：至少包含关键列（ts/open/high/low/close/volume/amount）
    need = {"ts","open","high","low","close","volume","amount"}
    assert need.issubset(set(y.columns)), f"columns missing required: {need - set(y.columns)}"
    # 断言：行数正确
    assert len(y) == 2
    # 断言：amount 缺失时填 NA
    assert y["amount"].isna().all()
    # 允许存在 turnover_rate 列（有则为数值/NA；无则不作硬性要求）
    # 这里不做强约束，仅验证逻辑不抛错

def test_norm_daily_df_basic():
    """日线归一化：中文列名可用，ts 升序、关键列完整。"""
    f = importlib.import_module("backend.datasource.fetchers")  # 导入统一归一化实现
    # 构造日线示例
    df = pd.DataFrame({
        "日期": ["2025-01-02","2025-01-03"],
        "开盘": [10,11],
        "最高": [11,12],
        "最低": [9.5,10.5],
        "收盘": [10.5,11.5],
        "成交量": [1000,2000],
        "成交额": [1e6, 2e6],
    })
    y = f._norm_daily_df(df)  # 调用归一化
    # 断言：两行，时间戳递增
    assert len(y) == 2
    assert y["ts"].iloc[0] < y["ts"].iloc[1]
    # 断言：关键列存在
    need = {"ts","open","high","low","close","volume","amount"}
    assert need.issubset(set(y.columns)), f"columns missing required: {need - set(y.columns)}"
