# backend/dev_tests/tdx_remote/test_bj_hq_market2_probe.py
# ==============================
# BJ 普通 HQ 专项测试
#
# 目标：
#   - 验证普通 HQ 是否支持 market=2 的 BJ 行情
#   - 测试：
#       1) security_bars day(category=4)
#       2) security_bars 1m(category=8)
#       3) security_bars 5m(category=0)
#       4) quote
#
# 说明：
#   - 本测试故意绕过正式 bars.py 中当前对 BJ 的限制
#   - 直接调用普通 HQ client + protocol 最底层
#   - 用于确认“BJ 是否真的走普通 HQ + market=2”
#
# 运行方式：
#   python -m backend.dev_tests.tdx_remote.test_bj_hq_market2_probe
# ==============================

from __future__ import annotations

import asyncio
import json
from typing import Dict, Any, List

import pandas as pd

from backend.datasource.providers.tdx_remote_adapter.client import TdxRemoteClient
from backend.datasource.providers.tdx_remote_adapter.protocol import (
    build_security_bars_request,
    parse_security_bars_body,
    build_security_bars_request as build_quote_like_dummy_request,  # 只是避免未引用告警，不会实际用于 quote
)

# 注意：我们这里直接手写 quote 请求，不走现有 bars 原子接口
# 因为要绕过 bj 限制，验证 protocol 原始能力


BJ_CODES = [
    "920000",
    "920992",
    "430047",
    "830799",
]

MARKET_BJ = 2

BAR_CASES = [
    {"name": "day", "category": 4, "count": 20},
    {"name": "1m", "category": 8, "count": 20},
    {"name": "5m", "category": 0, "count": 20},
]


def _sample_df(df: pd.DataFrame) -> Dict[str, Any]:
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


def _build_quote_request_bj(code: str) -> bytes:
    """
    直接按普通 HQ 的 quote 请求结构构包，强行使用 market=2。
    这里参考你现有项目中的 GetSecurityQuotes / quote.Frame 思路：
      data 前缀固定：
        05 00 00 00 00 00 00 00 + count(2字节)
      然后每个标的：
        market(1字节) + code(6字节)
    """
    s = str(code or "").strip()
    if not s or len(s) > 6:
        raise ValueError(f"invalid bj code for quote probe: {code}")

    code6 = s.encode("ascii")
    payload = bytearray()
    payload.extend(b"\x05\x00\x00\x00\x00\x00\x00\x00")
    payload.extend((1).to_bytes(2, byteorder="little", signed=False))
    payload.extend(MARKET_BJ.to_bytes(1, byteorder="little", signed=False))
    payload.extend(code6)

    total_len = len(payload)
    frame = bytearray()
    frame.extend(b"\x0c")
    frame.extend((0).to_bytes(4, byteorder="little", signed=False))
    frame.extend(b"\x01")
    frame.extend(total_len.to_bytes(2, byteorder="little", signed=False))
    frame.extend(total_len.to_bytes(2, byteorder="little", signed=False))
    frame.extend((0x053E).to_bytes(2, byteorder="little", signed=False))
    frame.extend(payload)
    return bytes(frame)


def _decode_quote_body_minimal(body: bytes) -> Dict[str, Any]:
    """
    这里只做最小验证，不完整解析整个 quote 结构：
      - 记录 body 长度
      - 尝试读出返回股票数量
      - 保留前 64 字节 hex 预览
    目的：先确认 market=2 quote 通道是否有真实响应，不在此阶段深挖完整字段。
    """
    if body is None:
        return {
            "body_len": 0,
            "count_guess": None,
            "preview_hex": "",
        }

    body_len = len(body)
    count_guess = None
    if body_len >= 4:
        try:
            count_guess = int.from_bytes(body[2:4], byteorder="little", signed=False)
        except Exception:
            count_guess = None

    return {
        "body_len": body_len,
        "count_guess": count_guess,
        "preview_hex": body[:64].hex(),
    }


def _probe_bj_code_sync(code: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "code": code,
        "market": MARKET_BJ,
        "quote": None,
        "bars": [],
    }

    with TdxRemoteClient() as client:
        client.connect()

        # 1) quote
        try:
            quote_req = _build_quote_request_bj(code)
            quote_body = client.request_raw(quote_req)
            out["quote"] = {
                "success": True,
                "error": None,
                **_decode_quote_body_minimal(quote_body),
            }
        except Exception as e:
            out["quote"] = {
                "success": False,
                "error": str(e),
                "body_len": 0,
                "count_guess": None,
                "preview_hex": "",
            }

        # 2) bars
        for case in BAR_CASES:
            item: Dict[str, Any] = {
                "name": case["name"],
                "category": case["category"],
                "count": case["count"],
                "success": False,
                "error": None,
                "rows": 0,
                "columns": [],
                "head5": [],
                "tail5": [],
            }

            try:
                req = build_security_bars_request(
                    category=int(case["category"]),
                    market=MARKET_BJ,
                    code=code,
                    start=0,
                    count=int(case["count"]),
                )
                body = client.request_raw(req)
                rows = parse_security_bars_body(body, category=int(case["category"]))
                df = pd.DataFrame(rows) if rows else pd.DataFrame()

                sampled = _sample_df(df)
                item["success"] = True
                item["rows"] = sampled["rows"]
                item["columns"] = sampled["columns"]
                item["head5"] = sampled["head5"]
                item["tail5"] = sampled["tail5"]

            except Exception as e:
                item["success"] = False
                item["error"] = str(e)

            out["bars"].append(item)

    return out


async def main_async() -> None:
    items: List[Dict[str, Any]] = []
    for code in BJ_CODES:
        items.append(await asyncio.to_thread(_probe_bj_code_sync, code))

    payload = {
        "ok": True,
        "test": "tdx_hq.bj_market2_probe",
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
