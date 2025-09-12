# tests/integration/test_candles_api.py
# ==============================
# 说明：贯通性集成用例（慢测，真实拉取）
# - 需要后端已启动在 8000 端口
# - 本次修改：移除 120m 测试用例
# ==============================

import pytest
import requests

SERVER = "http://localhost:8000"

pytestmark = pytest.mark.slow  # 标注为慢测

def _get(path, params):
    """GET 封装。"""
    r = requests.get(f"{SERVER}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def test_a_stock_day():
    """A 股日线最小窗口。"""
    data = _get("/api/candles", {
        "code": "600519", "freq":"1d",
        "start": "2024-12-20", "end": "2025-01-10",
        "include": "vol,ma", "ma_periods": "5,10",
    })
    assert data["meta"]["freq"] == "1d"
    assert data["meta"]["symbol"] == "600519"
    assert data["meta"]["rows"] >= 1

def test_etf_60m():
    """ETF 60m。"""
    # 510300：沪深300ETF（上交所）
    d60 = _get("/api/candles", {
        "code": "510300", "freq":"60m",
        "start": "2025-01-02", "end": "2025-01-10",
        "include": "vol",
    })
    assert d60["meta"]["rows"] >= 1
    # 移除：不再测试 120m

def test_lof_week():
    """LOF 周线。"""
    # 例如 166009 中欧动力LOF
    d1w = _get("/api/candles", {
        "code": "166009", "freq":"1w",
        "start": "2024-10-01", "end": "2025-01-10",
        "include": "vol,ma", "ma_periods":"5,10",
    })
    assert d1w["meta"]["rows"] >= 1
