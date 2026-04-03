# backend/services/minute_archive/codec.py
# ==============================
# 分钟线累积归档 - TDX 原生分钟记录编解码
#
# 职责：
#   - 逻辑分钟记录 <-> TDX 原生 32字节分钟记录
#   - 仅负责编码与解码
#   - 不负责路径、拼接、去重、写文件
#
# 当前支持：
#   - 1m -> .lc1
#   - 5m -> .lc5
#
# 统一逻辑输入记录格式：
#   - market : SH/SZ/BJ
#   - symbol : 证券代码
#   - freq   : 1m / 5m
#   - date   : YYYYMMDD int
#   - time   : HH:MM str
#   - open   : float
#   - high   : float
#   - low    : float
#   - close  : float
#   - amount : float
#   - volume : float
#
# 编码原则：
#   - 归档内部时间语义保持 TDX 原生 date_code + time_code
#   - 不引入 ts 到归档层
# ==============================

from __future__ import annotations

import struct
from typing import Dict, Any, List, Optional
from pathlib import Path

from backend.utils.time import parse_yyyymmdd

_RECORD_SIZE = 32

_FREQ_TO_SUFFIX = {
    "1m": ".lc1",
    "5m": ".lc5",
}

_SUFFIX_TO_FREQ = {
    ".lc1": "1m",
    ".lc5": "5m",
}


def get_suffix_by_freq(freq: str) -> str:
    f = str(freq or "").strip()
    suffix = _FREQ_TO_SUFFIX.get(f)
    if not suffix:
        raise ValueError(f"unsupported minute archive freq: {freq}")
    return suffix


def get_freq_by_suffix(path_or_suffix: str | Path) -> str:
    if isinstance(path_or_suffix, Path):
        suffix = str(path_or_suffix.suffix or "").strip().lower()
    else:
        suffix = str(path_or_suffix or "").strip().lower()
    freq = _SUFFIX_TO_FREQ.get(suffix)
    if not freq:
        raise ValueError(f"unsupported minute archive suffix: {suffix}")
    return freq


def encode_date_code(yyyymmdd: int) -> int:
    ymd = int(yyyymmdd)
    year = ymd // 10000
    month = (ymd // 100) % 100
    day = ymd % 100

    if not (2004 <= year <= 2035):
        raise ValueError(f"minute archive date out of supported range: {yyyymmdd}")
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError(f"invalid minute archive date: {yyyymmdd}")

    return (year - 2004) * 2048 + month * 100 + day


def decode_date_code(encoded: int) -> int:
    val = int(encoded)
    year = val // 2048 + 2004
    remain = val % 2048
    month = remain // 100
    day = remain % 100

    if not (2004 <= year <= 2035):
        raise ValueError(f"decoded minute archive year out of range: {year}")
    if not (1 <= month <= 12):
        raise ValueError(f"decoded minute archive month invalid: {month}")
    if not (1 <= day <= 31):
        raise ValueError(f"decoded minute archive day invalid: {day}")

    return year * 10000 + month * 100 + day


def encode_time_code(time_text: str) -> int:
    s = str(time_text or "").strip()
    if ":" not in s:
        raise ValueError(f"invalid minute archive time text: {time_text}")

    hh_str, mm_str = s.split(":", 1)
    try:
        hour = int(hh_str)
        minute = int(mm_str)
    except Exception:
        raise ValueError(f"invalid minute archive time text: {time_text}")

    if hour == 24 and minute == 0:
        return 24 * 60
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"invalid minute archive time text: {time_text}")

    return hour * 60 + minute


def decode_time_code(encoded: int) -> str:
    val = int(encoded)
    if not (0 <= val <= 24 * 60):
        raise ValueError(f"invalid minute archive time code: {encoded}")

    if val == 24 * 60:
        return "24:00"

    hour = val // 60
    minute = val % 60
    return f"{hour:02d}:{minute:02d}"


def normalize_minute_record(record: Dict[str, Any]) -> Dict[str, Any]:
    r = dict(record or {})

    market = str(r.get("market") or "").strip().upper()
    symbol = str(r.get("symbol") or "").strip()
    freq = str(r.get("freq") or "").strip()
    date_val = parse_yyyymmdd(r.get("date"))
    time_val = str(r.get("time") or "").strip()

    if market not in ("SH", "SZ", "BJ"):
        raise ValueError(f"invalid market in minute record: {market}")
    if not symbol or not symbol.isdigit():
        raise ValueError(f"invalid symbol in minute record: {symbol}")
    if freq not in ("1m", "5m"):
        raise ValueError(f"invalid freq in minute record: {freq}")

    try:
        open_v = float(r.get("open"))
        high_v = float(r.get("high"))
        low_v = float(r.get("low"))
        close_v = float(r.get("close"))
    except Exception:
        raise ValueError("minute record open/high/low/close must be numeric")

    try:
        amount_v = float(r.get("amount")) if r.get("amount") is not None else 0.0
    except Exception:
        amount_v = 0.0

    try:
        volume_v = float(r.get("volume")) if r.get("volume") is not None else 0.0
    except Exception:
        volume_v = 0.0

    _ = encode_time_code(time_val)  # 借此校验 time 合法

    return {
        "market": market,
        "symbol": symbol,
        "freq": freq,
        "date": int(date_val),
        "time": time_val,
        "open": float(open_v),
        "high": float(high_v),
        "low": float(low_v),
        "close": float(close_v),
        "amount": float(amount_v),
        "volume": float(volume_v),
    }


def encode_record_to_bytes(record: Dict[str, Any]) -> bytes:
    r = normalize_minute_record(record)

    date_code = encode_date_code(int(r["date"]))
    time_code = encode_time_code(str(r["time"]))

    volume_int = int(round(float(r["volume"])))
    if volume_int < 0:
        volume_int = 0

    return struct.pack(
        "<HHfffffII",
        int(date_code),
        int(time_code),
        float(r["open"]),
        float(r["high"]),
        float(r["low"]),
        float(r["close"]),
        float(r["amount"]),
        int(volume_int),
        0,  # reserved
    )


def decode_record_from_bytes(
    raw: bytes,
    *,
    market: str,
    symbol: str,
    freq: str,
) -> Dict[str, Any]:
    if not raw or len(raw) != _RECORD_SIZE:
        raise ValueError("invalid minute archive record bytes length")

    try:
        date_code, time_code = struct.unpack("<HH", raw[0:4])
        open_f, high_f, low_f, close_f, amount_f = struct.unpack("<fffff", raw[4:24])
        volume_i = struct.unpack("<I", raw[24:28])[0]
    except Exception as e:
        raise ValueError(f"failed to decode minute archive record: {e}") from e

    return {
        "market": str(market).strip().upper(),
        "symbol": str(symbol).strip(),
        "freq": str(freq).strip(),
        "date": decode_date_code(date_code),
        "time": decode_time_code(time_code),
        "open": float(open_f),
        "high": float(high_f),
        "low": float(low_f),
        "close": float(close_f),
        "amount": float(amount_f),
        "volume": float(int(volume_i)),
    }


def encode_records_to_bytes(records: List[Dict[str, Any]]) -> bytes:
    if not records:
        return b""
    return b"".join(encode_record_to_bytes(r) for r in records)
