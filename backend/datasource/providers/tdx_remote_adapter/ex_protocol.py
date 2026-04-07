# backend/datasource/providers/tdx_remote_adapter/ex_protocol.py
# ==============================
# TDX 扩展行情（ExHq）协议最小实现（修正版）
#
# 本轮关键修正：
#   - 使用真实 ex_setup_commands.py 中的 ExSetupCmd1 包
# ==============================

from __future__ import annotations

import struct
from typing import Dict, Any, List, Tuple

EXHQ_PORT = 7727
EXHQ_RSP_HEADER_LEN = 0x10
EXHQ_MAX_BARS_COUNT = 800
EXHQ_MAX_INSTRUMENT_INFO_COUNT = 500

def build_ex_setup_pkg1() -> bytes:
    return bytearray.fromhex(
        "01 01 48 65 00 01 52 00 52 00 54 24 1f 32 c6 e5"
        " d5 3d fb 41 1f 32 c6 e5 d5 3d fb 41 1f 32 c6 e5"
        " d5 3d fb 41 1f 32 c6 e5 d5 3d fb 41 1f 32 c6 e5"
        " d5 3d fb 41 1f 32 c6 e5 d5 3d fb 41 1f 32 c6 e5"
        " d5 3d fb 41 1f 32 c6 e5 d5 3d fb 41 cc e1 6d ff"
        " d5 ba 3f b8 cb c5 7a 05 4f 77 48 ea"
    )

def all_ex_setup_pkgs() -> List[bytes]:
    return [bytes(build_ex_setup_pkg1())]

def _encode_code9(code: str) -> bytes:
    s = str(code or "").strip()
    if not s:
        raise ValueError("tdx exhq protocol: empty code")
    if len(s) > 9:
        raise ValueError(f"tdx exhq protocol: code too long: {code}")
    return s.encode("ascii")

def build_ex_get_markets_request() -> bytes:
    return bytearray.fromhex("01 02 48 69 00 01 02 00 02 00 f4 23")

def build_ex_get_instrument_count_request() -> bytes:
    return bytearray.fromhex("01 03 48 66 00 01 02 00 02 00 f0 23")

def build_ex_get_instrument_info_request(*, start: int, count: int = 100) -> bytes:
    pkg = bytearray.fromhex("01 04 48 67 00 01 08 00 08 00 f5 23")
    pkg.extend(struct.pack("<IH", int(start), int(count)))
    return bytes(pkg)

def build_ex_get_instrument_quote_request(*, market: int, code: str) -> bytes:
    pkg = bytearray.fromhex("01 01 08 02 02 01 0c 00 0c 00 fa 23")
    code9 = _encode_code9(code)
    pkg.extend(struct.pack("<B9s", int(market), code9))
    return bytes(pkg)

def build_ex_get_instrument_bars_request(
    *,
    category: int,
    market: int,
    code: str,
    start: int,
    count: int,
) -> bytes:
    pkg = bytearray.fromhex("01 01 08 6a 01 01 16 00 16 00")
    pkg.extend(bytearray.fromhex("ff 23"))
    code9 = _encode_code9(code)
    pkg.extend(
        struct.pack(
            "<B9sHHIH",
            int(market),
            code9,
            int(category),
            1,
            int(start),
            int(count),
        )
    )
    return bytes(pkg)

def _get_datetime(category: int, buffer_bytes: bytes, pos: int) -> Tuple[int, int, int, int, int, int]:
    year = 0
    month = 0
    day = 0
    hour = 15
    minute = 0

    if category < 4 or category == 7 or category == 8:
        zipday, tminutes = struct.unpack("<HH", buffer_bytes[pos: pos + 4])
        year = (zipday >> 11) + 2004
        month = int((zipday % 2048) / 100)
        day = (zipday % 2048) % 100
        hour = int(tminutes / 60)
        minute = tminutes % 60
    else:
        (zipday,) = struct.unpack("<I", buffer_bytes[pos: pos + 4])
        year = int(zipday / 10000)
        month = int((zipday % 10000) / 100)
        day = zipday % 100

    pos += 4
    return year, month, day, hour, minute, pos

def parse_ex_markets_body(body: bytes) -> List[Dict[str, Any]]:
    pos = 0
    if body is None or len(body) < 2:
        return []

    (cnt,) = struct.unpack("<H", body[pos: pos + 2])
    pos += 2

    result: List[Dict[str, Any]] = []
    for _ in range(cnt):
        if pos + 64 > len(body):
            break

        category, raw_name, market, raw_short_name, _, unknown_bytes = struct.unpack(
            "<B32sB2s26s2s",
            body[pos: pos + 64]
        )
        pos += 64

        if category == 0 and market == 0:
            continue

        result.append({
            "market": int(market),
            "category": int(category),
            "name": raw_name.decode("gbk", errors="ignore").rstrip("\x00"),
            "short_name": raw_short_name.decode("gbk", errors="ignore").rstrip("\x00"),
            "unknown_bytes_hex": unknown_bytes.hex(),
        })

    return result

def parse_ex_instrument_count_body(body: bytes) -> int:
    if body is None or len(body) < 23:
        return 0
    (num,) = struct.unpack("<I", body[19:23])
    return int(num)

def parse_ex_instrument_info_body(body: bytes) -> List[Dict[str, Any]]:
    pos = 0
    if body is None or len(body) < 6:
        return []

    start, count = struct.unpack("<IH", body[:6])
    pos += 6

    result: List[Dict[str, Any]] = []
    for _ in range(count):
        if pos + 64 > len(body):
            break

        category, market, unused_bytes, code_raw, name_raw, desc_raw = struct.unpack(
            "<BB3s9s17s9s",
            body[pos: pos + 40]
        )

        result.append({
            "category": int(category),
            "market": int(market),
            "code": code_raw.decode("gbk", errors="ignore").rstrip("\x00"),
            "name": name_raw.decode("gbk", errors="ignore").rstrip("\x00"),
            "desc": desc_raw.decode("gbk", errors="ignore").rstrip("\x00"),
            "unused_bytes_hex": unused_bytes.hex(),
        })

        pos += 64

    return result

def parse_ex_instrument_quote_body(body: bytes) -> List[Dict[str, Any]]:
    if body is None or len(body) < 20:
        return []

    pos = 0
    market, code = struct.unpack("<B9s", body[pos: pos + 10])
    pos += 10
    pos += 4

    (
        pre_close, open_price, high, low, price, kaicang, _,
        zongliang, xianliang, _, neipan, waipan,
        _, chicang,
        b1, b2, b3, b4, b5,
        bv1, bv2, bv3, bv4, bv5,
        a1, a2, a3, a4, a5,
        av1, av2, av3, av4, av5
    ) = struct.unpack("<fffffIIIIIIIIIfffffIIIIIfffffIIIII", body[pos: pos + 136])

    return [{
        "market": int(market),
        "code": code.decode("utf-8", errors="ignore").rstrip("\x00"),
        "pre_close": float(pre_close),
        "open": float(open_price),
        "high": float(high),
        "low": float(low),
        "price": float(price),
        "kaicang": int(kaicang),
        "zongliang": int(zongliang),
        "xianliang": int(xianliang),
        "neipan": int(neipan),
        "waipan": int(waipan),
        "chicang": int(chicang),
        "bid1": float(b1),
        "bid2": float(b2),
        "bid3": float(b3),
        "bid4": float(b4),
        "bid5": float(b5),
        "bid_vol1": int(bv1),
        "bid_vol2": int(bv2),
        "bid_vol3": int(bv3),
        "bid_vol4": int(bv4),
        "bid_vol5": int(bv5),
        "ask1": float(a1),
        "ask2": float(a2),
        "ask3": float(a3),
        "ask4": float(a4),
        "ask5": float(a5),
        "ask_vol1": int(av1),
        "ask_vol2": int(av2),
        "ask_vol3": int(av3),
        "ask_vol4": int(av4),
        "ask_vol5": int(av5),
    }]

def parse_ex_instrument_bars_body(body: bytes, *, category: int) -> List[Dict[str, Any]]:
    pos = 0
    if body is None or len(body) < 20:
        return []

    pos += 18
    if pos + 2 > len(body):
        return []

    (ret_count,) = struct.unpack("<H", body[pos: pos + 2])
    pos += 2

    rows: List[Dict[str, Any]] = []
    for _ in range(ret_count):
        if pos + 28 > len(body):
            break

        year, month, day, hour, minute, pos = _get_datetime(category, body, pos)

        if pos + 28 > len(body):
            break

        open_price, high, low, close, position, trade, price = struct.unpack(
            "<ffffIIf",
            body[pos: pos + 28]
        )
        (amount,) = struct.unpack("f", body[pos + 16: pos + 20])
        pos += 28

        rows.append({
            "open": float(open_price),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "position": int(position),
            "trade": int(trade),
            "price": float(price),
            "amount": float(amount),
            "year": int(year),
            "month": int(month),
            "day": int(day),
            "hour": int(hour),
            "minute": int(minute),
            "datetime": f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
        })

    return rows