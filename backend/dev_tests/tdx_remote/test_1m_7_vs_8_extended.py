# backend/dev_tests/tdx_remote/test_1m_7_vs_8_extended.py
# ==============================
# 第1批扩展测试 - 1m category 7 vs 8 扩大范围对比
#
# 作用：
#   - 对更多标的、更大窗口、更长时间范围测试 7/8 是否完全一致
#   - 重点观察：
#       * rows 是否一致
#       * 首尾时间是否一致
#       * 首尾各连续5条 OHLCVA 是否一致
#       * 是否存在一方异常而另一方正常
#
# 运行方式：
#   python -m backend.dev_tests.tdx_remote.test_1m_7_vs_8_extended
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
from backend.datasource.providers.tdx_remote_adapter.router import decide_tdx_bars_route

TEST_ITEMS = [
    {"market": "SH", "symbol": "600519"},
    {"market": "SZ", "symbol": "000001"},
    {"market": "SH", "symbol": "510300"},
    {"market": "SZ", "symbol": "159915"},
    {"market": "SH", "symbol": "000001"},   # 指数
    {"market": "SZ", "symbol": "399001"},   # 指数
]

COUNTS = [20, 100, 500, 800]

def _sample(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {
            "rows": 0,
            "columns": [],
            "head5": [],
            "tail5": [],
        }
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "head5": df.head(5).to_dict("records"),
        "tail5": df.tail(5).to_dict("records"),
    }

async def _fetch_auto_route(
    *,
    market: str,
    symbol: str,
    category: int,
    count: int,
) -> pd.DataFrame:
    route = decide_tdx_bars_route(symbol=symbol, market=market)
    if route == "index_bars":
        return await get_index_bars_tdx_remote(
            category=category,
            market=market,
            symbol=symbol,
            start=0,
            count=count,
        )
    return await get_security_bars_tdx_remote(
        category=category,
        market=market,
        symbol=symbol,
        start=0,
        count=count,
    )

async def _probe_one(item: Dict[str, Any], count: int) -> Dict[str, Any]:
    market = item["market"]
    symbol = item["symbol"]
    route = decide_tdx_bars_route(symbol=symbol, market=market)

    out: Dict[str, Any] = {
        "market": market,
        "symbol": symbol,
        "route": route,
        "count": count,
        "cat7": None,
        "cat8": None,
    }

    for category, key in [(7, "cat7"), (8, "cat8")]:
        try:
            df = await _fetch_auto_route(
                market=market,
                symbol=symbol,
                category=category,
                count=count,
            )
            sampled = _sample(df)
            out[key] = {
                "success": True,
                "error": None,
                "rows": sampled["rows"],
                "columns": sampled["columns"],
                "head5": sampled["head5"],
                "tail5": sampled["tail5"],
            }
        except Exception as e:
            out[key] = {
                "success": False,
                "error": str(e),
                "rows": 0,
                "columns": [],
                "head5": [],
                "tail5": [],
            }

    return out

async def main_async() -> None:
    items: List[Dict[str, Any]] = []
    for item in TEST_ITEMS:
        for count in COUNTS:
            items.append(await _probe_one(item, count))

    payload = {
        "ok": True,
        "test": "tdx_remote.1m_7_vs_8_extended",
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()