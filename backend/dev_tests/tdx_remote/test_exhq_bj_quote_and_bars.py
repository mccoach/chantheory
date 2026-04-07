# backend/dev_tests/tdx_remote/test_exhq_bj_quote_and_bars.py
# ==============================
# ExHq 测试 - 在已知候选 market 上验证 BJ quote/bars
# ==============================

from __future__ import annotations

import asyncio
import json
from typing import Dict, Any, List

from backend.datasource.providers.tdx_remote_adapter.hosts import (
    sync_hosts_from_connect_cfg_if_needed,
    ensure_host_pool,
)
from backend.datasource.providers.tdx_remote_adapter.ex_client import TdxExRemoteClient
from backend.datasource.providers.tdx_remote_adapter.ex_protocol import (
    EXHQ_PORT,
    build_ex_get_instrument_quote_request,
    parse_ex_instrument_quote_body,
    build_ex_get_instrument_bars_request,
    parse_ex_instrument_bars_body,
)

BJ_CANDIDATES = [
    {"market": None, "code": "920000"},
    {"market": None, "code": "430047"},
    {"market": None, "code": "830799"},
]

BAR_CATEGORIES = [4, 8, 0]

async def _probe_one(host_item: Dict[str, Any], market: int, code: str) -> Dict[str, Any]:
    host = str(host_item.get("ip") or "").strip()
    port = int(host_item.get("port") or EXHQ_PORT)

    out: Dict[str, Any] = {
        "source": host_item,
        "host": host,
        "port": port,
        "market": market,
        "code": code,
        "quote": None,
        "bars": [],
    }

    try:
        def _sync_run() -> Dict[str, Any]:
            result: Dict[str, Any] = {
                "quote": None,
                "bars": [],
            }

            with TdxExRemoteClient(host=host, port=port) as client:
                client.connect()

                quote_req = build_ex_get_instrument_quote_request(
                    market=market,
                    code=code,
                )
                quote_body = client.request_raw(quote_req)
                quote_rows = parse_ex_instrument_quote_body(quote_body)
                result["quote"] = quote_rows

                bar_items: List[Dict[str, Any]] = []
                for category in BAR_CATEGORIES:
                    bar_req = build_ex_get_instrument_bars_request(
                        category=category,
                        market=market,
                        code=code,
                        start=0,
                        count=20,
                    )
                    bar_body = client.request_raw(bar_req)
                    bar_rows = parse_ex_instrument_bars_body(bar_body, category=category)

                    bar_items.append({
                        "category": category,
                        "rows": len(bar_rows),
                        "head5": bar_rows[:5],
                        "tail5": bar_rows[-5:] if bar_rows else [],
                    })

                result["bars"] = bar_items

            return result

        result = await asyncio.to_thread(_sync_run)
        out["quote"] = result["quote"]
        out["bars"] = result["bars"]

    except Exception as e:
        out["quote"] = {"error": str(e)}
        out["bars"] = []

    return out

async def main_async() -> None:
    ok, err = sync_hosts_from_connect_cfg_if_needed(force=True)
    if not ok:
        payload = {
            "ok": False,
            "test": "tdx_exhq.bj_quote_and_bars",
            "error": err,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    top3, top3_err = ensure_host_pool(
        pool_type="exhq",
        ping_timeout=1.0,
        force_retest=True,
    )

    items: List[Dict[str, Any]] = []

    for candidate in BJ_CANDIDATES:
        market = candidate.get("market")
        code = str(candidate.get("code") or "").strip()

        if market is None:
            items.append({
                "code": code,
                "skipped": True,
                "reason": "BJ_CANDIDATES.market is None, please fill actual market first",
            })
            continue

        if not top3_err and top3:
            for host_item in top3:
                items.append(await _probe_one(host_item, int(market), code))

    payload = {
        "ok": True,
        "test": "tdx_exhq.bj_quote_and_bars",
        "top3_error": top3_err,
        "top3_hosts": top3,
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()