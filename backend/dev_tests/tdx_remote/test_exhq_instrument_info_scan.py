# backend/dev_tests/tdx_remote/test_exhq_instrument_info_scan.py
# ==============================
# ExHq 测试 - 扫描扩展代码表，寻找 BJ 候选代码（基于统一 hosts 模块）
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
    build_ex_get_instrument_count_request,
    parse_ex_instrument_count_body,
    build_ex_get_instrument_info_request,
    parse_ex_instrument_info_body,
)

BJ_SYMBOLS = [
    "920000",
    "430047",
    "830799",
]

PAGE_SIZE = 500
MAX_PAGES = 80

async def _scan_one_host(item: Dict[str, Any]) -> Dict[str, Any]:
    host = str(item.get("ip") or "").strip()
    port = int(item.get("port") or EXHQ_PORT)

    out: Dict[str, Any] = {
        "source": item,
        "host": host,
        "port": port,
        "success": False,
        "error": None,
        "instrument_count": None,
        "matched_items": [],
        "scanned_pages": 0,
        "scanned_rows": 0,
    }

    try:
        def _sync_run() -> Dict[str, Any]:
            matched: List[Dict[str, Any]] = []
            scanned_rows = 0
            scanned_pages = 0
            instrument_count = None

            with TdxExRemoteClient(host=host, port=port) as client:
                client.connect()

                cnt_req = build_ex_get_instrument_count_request()
                cnt_body = client.request_raw(cnt_req)
                instrument_count = parse_ex_instrument_count_body(cnt_body)

                for page_idx in range(MAX_PAGES):
                    start = page_idx * PAGE_SIZE
                    req = build_ex_get_instrument_info_request(
                        start=start,
                        count=PAGE_SIZE,
                    )
                    body = client.request_raw(req)
                    rows = parse_ex_instrument_info_body(body)

                    scanned_pages += 1
                    scanned_rows += len(rows)

                    if not rows:
                        break

                    for row in rows:
                        code = str(row.get("code") or "").strip()
                        if code in BJ_SYMBOLS:
                            matched.append(dict(row))

            return {
                "instrument_count": instrument_count,
                "matched_items": matched,
                "scanned_pages": scanned_pages,
                "scanned_rows": scanned_rows,
            }

        result = await asyncio.to_thread(_sync_run)

        out["success"] = True
        out["instrument_count"] = result["instrument_count"]
        out["matched_items"] = result["matched_items"]
        out["scanned_pages"] = result["scanned_pages"]
        out["scanned_rows"] = result["scanned_rows"]

    except Exception as e:
        out["success"] = False
        out["error"] = str(e)

    return out

async def main_async() -> None:
    ok, err = sync_hosts_from_connect_cfg_if_needed(force=True)
    if not ok:
        payload = {
            "ok": False,
            "test": "tdx_exhq.instrument_info_scan",
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
    if not top3_err and top3:
        for item in top3:
            items.append(await _scan_one_host(item))

    payload = {
        "ok": True,
        "test": "tdx_exhq.instrument_info_scan",
        "target_symbols": BJ_SYMBOLS,
        "top3_error": top3_err,
        "top3_hosts": top3,
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()