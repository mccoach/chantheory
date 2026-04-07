# backend/dev_tests/tdx_remote/test_security_vs_index_route.py
# ==============================
# 第1批 TDX 远程测试 - security/index 路由对比
#
# 作用：
#   - 同一标的同时走 security_bars / index_bars
#   - 对比哪条更合理
#   - 返回首尾各连续5条
#
# 运行方式（示例）：
#   python -m backend.dev_tests.tdx_remote.test_security_vs_index_route
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

TEST_ITEMS = [
    {"market": "SH", "symbol": "600519", "daily_category": 4},
    {"market": "SZ", "symbol": "000001", "daily_category": 4},
    {"market": "SH", "symbol": "510300", "daily_category": 4},
    {"market": "SZ", "symbol": "159915", "daily_category": 4},
    {"market": "SH", "symbol": "000001", "daily_category": 4},
    {"market": "SZ", "symbol": "399001", "daily_category": 4},
]

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

async def _probe_one(market: str, symbol: str, category: int) -> Dict[str, Any]:
    out = {
        "market": market,
        "symbol": symbol,
        "category": category,
        "security_bars": None,
        "index_bars": None,
    }

    try:
        df_sec = await get_security_bars_tdx_remote(
            category=category,
            market=market,
            symbol=symbol,
            start=0,
            count=20,
        )
        out["security_bars"] = {
            "success": True,
            "error": None,
            **_sample(df_sec),
        }
    except Exception as e:
        out["security_bars"] = {
            "success": False,
            "error": str(e),
            "rows": 0,
            "columns": [],
            "head5": [],
            "tail5": [],
        }

    try:
        df_idx = await get_index_bars_tdx_remote(
            category=category,
            market=market,
            symbol=symbol,
            start=0,
            count=20,
        )
        out["index_bars"] = {
            "success": True,
            "error": None,
            **_sample(df_idx),
        }
    except Exception as e:
        out["index_bars"] = {
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
        items.append(
            await _probe_one(
                market=item["market"],
                symbol=item["symbol"],
                category=int(item["daily_category"]),
            )
        )

    payload = {
        "ok": True,
        "test": "tdx_remote.security_vs_index_route",
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()