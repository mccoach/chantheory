# backend/dev_tests/tdx_remote/test_bj_market_probe.py
# ==============================
# 第1批扩展测试 - BJ 行情接口探索
#
# 作用：
#   - 先不做任何主观 market 映射结论
#   - 直接试探：
#       * security_bars / index_bars
#       * market=0 / market=1
#       * category=4 / 8 / 0
#   - 看是否存在某种可返回合理数据的组合
#
# 说明：
#   - 这个测试故意不走正式 bars.py 里的市场映射限制
#   - 直接调用 protocol/client 最底层，探索 BJ 的真实可用组合
#
# 运行方式：
#   python -m backend.dev_tests.tdx_remote.test_bj_market_probe
# ==============================

from __future__ import annotations

import asyncio
import json
from typing import Dict, Any, List

import pandas as pd

from backend.datasource.providers.tdx_remote_adapter.client import TdxRemoteClient
from backend.datasource.providers.tdx_remote_adapter.protocol import (
    build_security_bars_request,
    build_index_bars_request,
    parse_security_bars_body,
    parse_index_bars_body,
)

# 这里你可以按自己 symbol_index 里存在的 BJ 代码替换
BJ_SYMBOLS = [
    "920000",
    "430047",
    "830799",
]

MARKET_CANDIDATES = [2]
CATEGORY_CANDIDATES = [4, 8, 0]

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

def _fetch_raw_sync(
    *,
    method: str,
    market_int: int,
    symbol: str,
    category: int,
    count: int,
) -> pd.DataFrame:
    with TdxRemoteClient() as client:
        client.connect()

        if method == "security_bars":
            req = build_security_bars_request(
                category=category,
                market=market_int,
                code=symbol,
                start=0,
                count=count,
            )
            body = client.request_raw(req)
            rows = parse_security_bars_body(body, category=category)
        else:
            req = build_index_bars_request(
                category=category,
                market=market_int,
                code=symbol,
                start=0,
                count=count,
            )
            body = client.request_raw(req)
            rows = parse_index_bars_body(body, category=category)

    return pd.DataFrame(rows) if rows else pd.DataFrame()

async def _probe_one(symbol: str, method: str, market_int: int, category: int) -> Dict[str, Any]:
    out = {
        "symbol": symbol,
        "method": method,
        "market_int": market_int,
        "category": category,
        "success": False,
        "error": None,
        "rows": 0,
        "columns": [],
        "head5": [],
        "tail5": [],
    }

    try:
        df = await asyncio.to_thread(
            _fetch_raw_sync,
            method=method,
            market_int=market_int,
            symbol=symbol,
            category=category,
            count=20,
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

    for symbol in BJ_SYMBOLS:
        for method in ["security_bars", "index_bars"]:
            for market_int in MARKET_CANDIDATES:
                for category in CATEGORY_CANDIDATES:
                    items.append(
                        await _probe_one(
                            symbol=symbol,
                            method=method,
                            market_int=market_int,
                            category=category,
                        )
                    )

    payload = {
        "ok": True,
        "test": "tdx_remote.bj_market_probe",
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()