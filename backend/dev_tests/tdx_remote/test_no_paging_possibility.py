# backend/dev_tests/tdx_remote/test_no_paging_possibility.py
# ==============================
# 第1批扩展测试 - 探索 bars 是否存在“不分页即可全量”可能
#
# 作用：
#   - 对日线和分钟线尝试超过 800 的 count
#   - 看服务端是否：
#       * 直接报错
#       * 自动截断到800
#       * 返回超过800
#       * 返回异常脏数据
#
# 运行方式：
#   python -m backend.dev_tests.tdx_remote.test_no_paging_possibility
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
    {"market": "SH", "symbol": "600519", "daily_category": 4, "minute_category": 8},
    {"market": "SZ", "symbol": "000001", "daily_category": 4, "minute_category": 8},
    {"market": "SH", "symbol": "000001", "daily_category": 4, "minute_category": 8},   # 指数
]

COUNTS = [801, 1000, 1200, 1600, 2000]

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

async def _probe_one(item: Dict[str, Any], freq_kind: str, category: int, count: int) -> Dict[str, Any]:
    market = item["market"]
    symbol = item["symbol"]
    route = decide_tdx_bars_route(symbol=symbol, market=market)

    out = {
        "market": market,
        "symbol": symbol,
        "route": route,
        "freq_kind": freq_kind,
        "category": category,
        "count": count,
        "success": False,
        "error": None,
        "rows": 0,
        "columns": [],
        "head5": [],
        "tail5": [],
    }

    try:
        df = await _fetch_auto_route(
            market=market,
            symbol=symbol,
            category=category,
            count=count,
        )
        sampled = _sample(df)
        out["success"] = True
        out["rows"] = sampled["rows"]
        out["columns"] = sampled["columns"]
        out["head5"] = sampled["head5"]
        out["tail5"] = sampled["tail5"]
    except Exception as e:
        out["success"] = False
        out["error"] = str(e)

    return out

async def main_async() -> None:
    items: List[Dict[str, Any]] = []

    for item in TEST_ITEMS:
        for count in COUNTS:
            items.append(await _probe_one(item, "daily", int(item["daily_category"]), count))
            items.append(await _probe_one(item, "minute", int(item["minute_category"]), count))

    payload = {
        "ok": True,
        "test": "tdx_remote.no_paging_possibility",
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()