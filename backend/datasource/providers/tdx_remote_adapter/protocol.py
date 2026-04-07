# backend/datasource/providers/tdx_remote_adapter/protocol.py
# ==============================
# TDX 远程协议最小实现
#
# 职责：
#   - setup 握手包构造
#   - bars 请求包构造
#   - 响应头解析
#   - 响应体解压
#   - security_bars / index_bars 响应体解析
#
# 设计原则：
#   - 只做协议层，不做 socket 生命周期
#   - 只做 bytes <-> python 原始结构
#   - 不做 DataFrame 落库逻辑
#
# 说明：
#   - 参考了 pytdx 的协议思路，但不依赖 pytdx 运行时包
#   - 当前只实现本项目现阶段需要的最小协议能力
# ==============================

from __future__ import annotations

import struct
import zlib
from typing import Dict, Any, List, Tuple

# ==========================================================
# 一、TDX 常量
# ==========================================================

MARKET_SZ = 0
MARKET_SH = 1

KLINE_TYPE_5MIN = 0
KLINE_TYPE_15MIN = 1
KLINE_TYPE_30MIN = 2
KLINE_TYPE_1HOUR = 3
KLINE_TYPE_DAILY = 4
KLINE_TYPE_WEEKLY = 5
KLINE_TYPE_MONTHLY = 6
KLINE_TYPE_EXHQ_1MIN = 7
KLINE_TYPE_1MIN = 8
KLINE_TYPE_RI_K = 9
KLINE_TYPE_3MONTH = 10
KLINE_TYPE_YEARLY = 11

MAX_KLINE_COUNT_PER_REQUEST = 800
RSP_HEADER_LEN = 0x10

# ==========================================================
# 二、setup 握手包
# ==========================================================

def build_setup_pkg1() -> bytes:
    return bytearray.fromhex("0c 02 18 93 00 01 03 00 03 00 0d 00 01")

def build_setup_pkg2() -> bytes:
    return bytearray.fromhex("0c 02 18 94 00 01 03 00 03 00 0d 00 02")

def build_setup_pkg3() -> bytes:
    return bytearray.fromhex(
        "0c 03 18 99 00 01 20 00 20 00 db 0f d5"
        " d0 c9 cc d6 a4 a8 af 00 00 00 8f c2 25"
        " 40 13 00 00 d5 00 c9 cc bd f0 d7 ea 00"
        " 00 00 02"
    )

def all_setup_pkgs() -> List[bytes]:
    return [
        bytes(build_setup_pkg1()),
        bytes(build_setup_pkg2()),
        bytes(build_setup_pkg3()),
    ]

# ==========================================================
# 三、bars 请求包构造
# ==========================================================

def _encode_code6(code: str) -> bytes:
    s = str(code or "").strip()
    if not s:
        raise ValueError("tdx protocol: empty code")
    if len(s) > 6:
        raise ValueError(f"tdx protocol: code too long: {code}")
    return s.encode("ascii")

def build_security_bars_request(
    *,
    category: int,
    market: int,
    code: str,
    start: int,
    count: int,
) -> bytes:
    code6 = _encode_code6(code)

    values = (
        0x10C,
        0x01016408,
        0x1C,
        0x1C,
        0x052D,
        int(market),
        code6,
        int(category),
        1,
        int(start),
        int(count),
        0,
        0,
        0,
    )
    return struct.pack("<HIHHHH6sHHHHIIH", *values)

def build_index_bars_request(
    *,
    category: int,
    market: int,
    code: str,
    start: int,
    count: int,
) -> bytes:
    # 当前协议包结构与 security bars 一致，只是响应解析不同
    return build_security_bars_request(
        category=category,
        market=market,
        code=code,
        start=start,
        count=count,
    )

# ==========================================================
# 四、响应头与 body 处理
# ==========================================================

def parse_rsp_header(header: bytes) -> Dict[str, int]:
    if not header or len(header) != RSP_HEADER_LEN:
        raise ValueError(f"tdx protocol: invalid header length={len(header) if header else 0}")

    v1, v2, v3, zip_size, unzip_size = struct.unpack("<IIIHH", header)
    return {
        "v1": int(v1),
        "v2": int(v2),
        "v3": int(v3),
        "zip_size": int(zip_size),
        "unzip_size": int(unzip_size),
    }

def maybe_unzip_body(body: bytes, *, zip_size: int, unzip_size: int) -> bytes:
    if body is None:
        raise ValueError("tdx protocol: body is None")
    if len(body) != int(zip_size):
        raise ValueError(
            f"tdx protocol: body size mismatch actual={len(body)} expected_zip={zip_size}"
        )

    if int(zip_size) == int(unzip_size):
        return body

    try:
        return zlib.decompress(body)
    except Exception as e:
        raise ValueError(f"tdx protocol: body unzip failed: {e}") from e

# ==========================================================
# 五、基础解析辅助
# ==========================================================

def _index_byte(data: bytes, pos: int) -> int:
    return data[pos]

def _get_price(data: bytes, pos: int) -> Tuple[int, int]:
    pos_byte = 6
    bdata = _index_byte(data, pos)
    intdata = bdata & 0x3F
    sign = bool(bdata & 0x40)

    if bdata & 0x80:
        while True:
            pos += 1
            bdata = _index_byte(data, pos)
            intdata += (bdata & 0x7F) << pos_byte
            pos_byte += 7
            if bdata & 0x80:
                continue
            break

    pos += 1

    if sign:
        intdata = -intdata

    return intdata, pos

def _get_volume(ivol: int) -> float:
    logpoint = ivol >> (8 * 3)
    hleax = (ivol >> (8 * 2)) & 0xFF
    lheax = (ivol >> 8) & 0xFF
    lleax = ivol & 0xFF

    dw_ecx = logpoint * 2 - 0x7F
    dw_edx = logpoint * 2 - 0x86
    dw_esi = logpoint * 2 - 0x8E
    dw_eax = logpoint * 2 - 0x96

    tmp = -dw_ecx if dw_ecx < 0 else dw_ecx
    dbl_xmm6 = pow(2.0, tmp)
    if dw_ecx < 0:
        dbl_xmm6 = 1.0 / dbl_xmm6

    if hleax > 0x80:
        tmpdbl = pow(2.0, dw_edx + 1)
        dbl_xmm0 = pow(2.0, dw_edx) * 128.0
        dbl_xmm0 += (hleax & 0x7F) * tmpdbl
        dbl_xmm4 = dbl_xmm0
    else:
        if dw_edx >= 0:
            dbl_xmm0 = pow(2.0, dw_edx) * hleax
        else:
            dbl_xmm0 = (1 / pow(2.0, dw_edx)) * hleax
        dbl_xmm4 = dbl_xmm0

    dbl_xmm3 = pow(2.0, dw_esi) * lheax
    dbl_xmm1 = pow(2.0, dw_eax) * lleax

    if hleax & 0x80:
        dbl_xmm3 *= 2.0
        dbl_xmm1 *= 2.0

    return float(dbl_xmm6 + dbl_xmm4 + dbl_xmm3 + dbl_xmm1)

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

# ==========================================================
# 六、bars body 解析
# ==========================================================

def parse_security_bars_body(body: bytes, *, category: int) -> List[Dict[str, Any]]:
    if body is None or len(body) < 2:
        return []

    pos = 0
    (ret_count,) = struct.unpack("<H", body[0:2])
    pos += 2

    rows: List[Dict[str, Any]] = []
    pre_diff_base = 0

    for _ in range(ret_count):
        year, month, day, hour, minute, pos = _get_datetime(category, body, pos)

        price_open_diff, pos = _get_price(body, pos)
        price_close_diff, pos = _get_price(body, pos)
        price_high_diff, pos = _get_price(body, pos)
        price_low_diff, pos = _get_price(body, pos)

        (vol_raw,) = struct.unpack("<I", body[pos: pos + 4])
        vol = _get_volume(vol_raw)
        pos += 4

        (amount_raw,) = struct.unpack("<I", body[pos: pos + 4])
        amount = _get_volume(amount_raw)
        pos += 4

        open_v = float(price_open_diff + pre_diff_base) / 1000.0
        price_open_diff = price_open_diff + pre_diff_base

        close_v = float(price_open_diff + price_close_diff) / 1000.0
        high_v = float(price_open_diff + price_high_diff) / 1000.0
        low_v = float(price_open_diff + price_low_diff) / 1000.0

        pre_diff_base = price_open_diff + price_close_diff

        rows.append({
            "open": open_v,
            "close": close_v,
            "high": high_v,
            "low": low_v,
            "vol": float(vol),
            "amount": float(amount),
            "year": int(year),
            "month": int(month),
            "day": int(day),
            "hour": int(hour),
            "minute": int(minute),
            "datetime": f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
        })

    return rows

def parse_index_bars_body(body: bytes, *, category: int) -> List[Dict[str, Any]]:
    if body is None or len(body) < 2:
        return []

    pos = 0
    (ret_count,) = struct.unpack("<H", body[0:2])
    pos += 2

    rows: List[Dict[str, Any]] = []
    pre_diff_base = 0

    for _ in range(ret_count):
        year, month, day, hour, minute, pos = _get_datetime(category, body, pos)

        price_open_diff, pos = _get_price(body, pos)
        price_close_diff, pos = _get_price(body, pos)
        price_high_diff, pos = _get_price(body, pos)
        price_low_diff, pos = _get_price(body, pos)

        (vol_raw,) = struct.unpack("<I", body[pos: pos + 4])
        vol = _get_volume(vol_raw)
        pos += 4

        (amount_raw,) = struct.unpack("<I", body[pos: pos + 4])
        amount = _get_volume(amount_raw)
        pos += 4

        up_count, down_count = struct.unpack("<HH", body[pos: pos + 4])
        pos += 4

        open_v = float(price_open_diff + pre_diff_base) / 1000.0
        price_open_diff = price_open_diff + pre_diff_base

        close_v = float(price_open_diff + price_close_diff) / 1000.0
        high_v = float(price_open_diff + price_high_diff) / 1000.0
        low_v = float(price_open_diff + price_low_diff) / 1000.0

        pre_diff_base = price_open_diff + price_close_diff

        rows.append({
            "open": open_v,
            "close": close_v,
            "high": high_v,
            "low": low_v,
            "vol": float(vol),
            "amount": float(amount),
            "year": int(year),
            "month": int(month),
            "day": int(day),
            "hour": int(hour),
            "minute": int(minute),
            "datetime": f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
            "up_count": int(up_count),
            "down_count": int(down_count),
        })

    return rows