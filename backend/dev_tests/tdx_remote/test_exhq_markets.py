# backend/dev_tests/tdx_remote/test_exhq_markets.py
# ==============================
# ExHq 测试 - 获取扩展市场列表（基于统一 hosts 模块）
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
    build_ex_get_markets_request,
    parse_ex_markets_body,
)

def _pick_suspected_bj_markets(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keywords = ["北", "北京", "北交", "京", "三板", "NEEQ", "BSE", "BJ"]

    out: List[Dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "")
        short_name = str(row.get("short_name") or "")
        text = f"{name} {short_name}".upper()

        matched = False
        for kw in keywords:
            if kw.upper() in text:
                matched = True
                break

        if matched:
            out.append(dict(row))

    return out

async def _probe_one_host(item: Dict[str, Any]) -> Dict[str, Any]:
    host = str(item.get("ip") or "").strip()
    port = int(item.get("port") or EXHQ_PORT)

    out: Dict[str, Any] = {
        "source": item,
        "host": host,
        "port": port,
        "success": False,
        "error": None,
        "rows": 0,
        "suspected_bj_markets": [],
        "items": [],
    }

    try:
        def _sync_run() -> List[Dict[str, Any]]:
            with TdxExRemoteClient(host=host, port=port) as client:
                client.connect()
                req = build_ex_get_markets_request()
                body = client.request_raw(req)
                return parse_ex_markets_body(body)

        rows = await asyncio.to_thread(_sync_run)

        out["success"] = True
        out["rows"] = len(rows)
        out["items"] = rows
        out["suspected_bj_markets"] = _pick_suspected_bj_markets(rows)

    except Exception as e:
        out["success"] = False
        out["error"] = str(e)

    return out

async def main_async() -> None:
    ok, err = sync_hosts_from_connect_cfg_if_needed(force=True)
    if not ok:
        payload = {
            "ok": False,
            "test": "tdx_exhq.markets",
            "error": err,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    top3, top3_err = ensure_host_pool(
        pool_type="exhq",
        ping_timeout=1.0,
        force_retest=True,
    )

    # 若 top3 全失败，则退化为全量 DSHOST 直接从 json 里拿；这里暂时只输出 top3 结果
    items: List[Dict[str, Any]] = []
    if not top3_err and top3:
        for item in top3:
            items.append(await _probe_one_host(item))

    payload = {
        "ok": True,
        "test": "tdx_exhq.markets",
        "top3_error": top3_err,
        "top3_hosts": top3,
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()