# backend/dev_tests/tdx_remote/test_paging_and_window.py
# ==============================
# 第1批 TDX 远程测试 - 1d 分页 / 1m5m 窗口测试
#
# 作用：
#   - 测 1d 翻页方向和连续性
#   - 测 1m / 5m 单次可返回多少、时间能回溯到哪里
#
# 运行方式（示例）：
#   python -m backend.dev_tests.tdx_remote.test_paging_and_window
# ==============================

from __future__ import annotations

import asyncio
import json
from typing import Dict, Any, List

import pandas as pd

from backend.datasource.providers.tdx_remote_adapter.bars import get_security_bars_tdx_remote

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

async def _probe_day_paging(
    *,
    market: str,
    symbol: str,
    category: int,
) -> List[Dict[str, Any]]:
    pages = [
        {"start": 0, "count": 10},
        {"start": 0, "count": 800},
        {"start": 800, "count": 800},
        {"start": 1600, "count": 800},
    ]

    out = []
    for p in pages:
        item = {
            "market": market,
            "symbol": symbol,
            "category": category,
            "start": p["start"],
            "count": p["count"],
            "success": False,
            "error": None,
            "rows": 0,
            "columns": [],
            "head5": [],
            "tail5": [],
        }
        try:
            df = await get_security_bars_tdx_remote(
                category=category,
                market=market,
                symbol=symbol,
                start=p["start"],
                count=p["count"],
            )
            item["success"] = True
            item.update(_sample(df))
        except Exception as e:
            item["success"] = False
            item["error"] = str(e)

        out.append(item)

    return out

async def _probe_minute_window(
    *,
    market: str,
    symbol: str,
    category: int,
) -> List[Dict[str, Any]]:
    counts = [10, 100, 500, 800]

    out = []
    for c in counts:
        item = {
            "market": market,
            "symbol": symbol,
            "category": category,
            "start": 0,
            "count": c,
            "success": False,
            "error": None,
            "rows": 0,
            "columns": [],
            "head5": [],
            "tail5": [],
        }
        try:
            df = await get_security_bars_tdx_remote(
                category=category,
                market=market,
                symbol=symbol,
                start=0,
                count=c,
            )
            item["success"] = True
            item.update(_sample(df))
        except Exception as e:
            item["success"] = False
            item["error"] = str(e)

        out.append(item)

    return out

async def main_async() -> None:
    payload = {
        "ok": True,
        "test": "tdx_remote.paging_and_window",
        "day_paging": [],
        "minute_window": [],
    }

    payload["day_paging"] = await _probe_day_paging(
        market="SH",
        symbol="600519",
        category=4,
    )

    payload["minute_window"].append({
        "freq_hint": "1m_candidate_7",
        "items": await _probe_minute_window(
            market="SH",
            symbol="600519",
            category=7,
        ),
    })

    payload["minute_window"].append({
        "freq_hint": "1m_candidate_8",
        "items": await _probe_minute_window(
            market="SH",
            symbol="600519",
            category=8,
        ),
    })

    payload["minute_window"].append({
        "freq_hint": "5m_candidate_0",
        "items": await _probe_minute_window(
            market="SH",
            symbol="600519",
            category=0,
        ),
    })

    print(json.dumps(payload, ensure_ascii=False, indent=2))

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()