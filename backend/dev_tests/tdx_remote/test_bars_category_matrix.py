# backend/dev_tests/tdx_remote/test_bars_category_matrix.py
# ==============================
# 第1批 TDX 远程测试 - bars category 矩阵测试
#
# 作用：
#   - 对同一标的尝试多个 category
#   - 看哪些能成功返回
#   - 返回首尾各连续5条，便于人工判断真实频率
#
# 运行方式（示例）：
#   python -m backend.dev_tests.tdx_remote.test_bars_category_matrix
# ==============================

from __future__ import annotations

import asyncio
import json
from typing import Dict, Any, List

import pandas as pd

from backend.datasource.providers.tdx_remote_adapter.bars import (
    get_security_bars_tdx_remote,
    get_index_bars_tdx_remote,
)

CATEGORIES = [0, 1, 2, 3, 4, 7, 8, 9]

TEST_ITEMS = [
    {"market": "SH", "symbol": "600519", "method": "security_bars"},
    {"market": "SZ", "symbol": "000001", "method": "security_bars"},
    {"market": "SH", "symbol": "510300", "method": "security_bars"},
    {"market": "SZ", "symbol": "159915", "method": "security_bars"},
    {"market": "SH", "symbol": "000001", "method": "index_bars"},
    {"market": "SZ", "symbol": "399001", "method": "index_bars"},
]

def _sample_head_tail(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {
            "rows": 0,
            "columns": [],
            "head5": [],
            "tail5": [],
        }

    head5 = df.head(2).to_dict("records")
    tail5 = df.tail(2).to_dict("records")

    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "head5": head5,
        "tail5": tail5,
    }

async def _run_one(item: Dict[str, Any], category: int) -> Dict[str, Any]:
    market = item["market"]
    symbol = item["symbol"]
    method = item["method"]

    result: Dict[str, Any] = {
        "market": market,
        "symbol": symbol,
        "method": method,
        "category": category,
        "success": False,
        "error": None,
        "rows": 0,
        "columns": [],
        "head5": [],
        "tail5": [],
    }

    try:
        if method == "security_bars":
            df = await get_security_bars_tdx_remote(
                category=category,
                market=market,
                symbol=symbol,
                start=0,
                count=20,
            )
        else:
            df = await get_index_bars_tdx_remote(
                category=category,
                market=market,
                symbol=symbol,
                start=0,
                count=20,
            )

        sampled = _sample_head_tail(df)
        result["success"] = True
        result["rows"] = sampled["rows"]
        result["columns"] = sampled["columns"]
        result["head5"] = sampled["head5"]
        result["tail5"] = sampled["tail5"]

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result

async def main_async() -> None:
    items: List[Dict[str, Any]] = []

    for item in TEST_ITEMS:
        for category in CATEGORIES:
            items.append(await _run_one(item, category))

    payload = {
        "ok": True,
        "test": "tdx_remote.bars_category_matrix",
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()