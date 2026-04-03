# backend/datasource/local_files/tdx_minute.py
# ==============================
# TDX 本地 .lc1 / .lc5 文件解析器
#
# 职责：
#   - 解析单个通达信分钟线文件（.lc1 / .lc5）
#   - 返回原始分钟K线 DataFrame
#
# 当前阶段范围：
#   - 支持 .lc1 -> 1m
#   - 支持 .lc5 -> 5m
#   - 一条记录 = 一根分钟K线
#   - 不做业务标准化
#   - 不做写库
#   - 不做路径扫描
#
# 输出原始字段：
#   - date          : YYYYMMDD 整数
#   - time          : HH:MM 字符串（K线区间结束时刻）
#   - open          : float（元）
#   - high          : float（元）
#   - low           : float（元）
#   - close         : float（元）
#   - amount        : float（元）
#   - volume        : float（股）
#
# 通达信 .lc1 / .lc5 记录格式（32字节）：
#   1. date_code    2字节 uint16，自定义压缩日期编码
#   2. time_code    2字节 uint16，从 00:00 起的分钟数
#   3. open         4字节 float，开盘价（元）
#   4. high         4字节 float，最高价（元）
#   5. low          4字节 float，最低价（元）
#   6. close        4字节 float，收盘价（元）
#   7. amount       4字节 float，成交额（元）
#   8. volume       4字节 uint32，成交量（股）
#   9. reserved     4字节 uint32，保留字段（当前观测为 0）
#
# 日期编码规则：
#   encoded = (year - 2004) * 2048 + month * 100 + day
# 解码规则：
#   year  = encoded // 2048 + 2004
#   month = (encoded % 2048) // 100
#   day   = (encoded % 2048) % 100
# ==============================

from __future__ import annotations

import struct
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

from backend.utils.logger import get_logger

_LOG = get_logger("local_files.tdx_minute")

_MINUTE_RECORD_SIZE = 32
_SUPPORTED_EXT_TO_FREQ = {
    ".lc1": "1m",
    ".lc5": "5m",
}


def _decode_date_code(encoded: int) -> Optional[int]:
    """
    将 TDX 分钟线压缩日期编码解码为 YYYYMMDD 整数。
    """
    try:
        val = int(encoded)
    except Exception:
        return None

    year = val // 2048 + 2004
    remain = val % 2048
    month = remain // 100
    day = remain % 100

    if not (2004 <= year <= 2035):
        return None
    if not (1 <= month <= 12):
        return None
    if not (1 <= day <= 31):
        return None

    return year * 10000 + month * 100 + day


def _decode_time_code(encoded: int) -> Optional[str]:
    """
    将分钟数编码解码为 HH:MM 字符串。
    """
    try:
        val = int(encoded)
    except Exception:
        return None

    if not (0 <= val <= 24 * 60):
        return None

    hour = val // 60
    minute = val % 60

    if not (0 <= hour <= 23 or (hour == 24 and minute == 0)):
        return None

    if hour == 24 and minute == 0:
        return "24:00"

    return f"{hour:02d}:{minute:02d}"


def _detect_freq_from_suffix(path: Path) -> str:
    ext = str(path.suffix or "").strip().lower()
    freq = _SUPPORTED_EXT_TO_FREQ.get(ext)
    if not freq:
        raise ValueError(f"unsupported minute file suffix: {path.name}")
    return freq


def load_tdx_minute_df(file_path: Path | str) -> pd.DataFrame:
    """
    解析单个 .lc1 / .lc5 文件并返回原始分钟K线 DataFrame。

    Args:
        file_path: .lc1 / .lc5 文件路径

    Returns:
        DataFrame(columns=[
            'date', 'time', 'open', 'high', 'low', 'close', 'amount', 'volume'
        ])

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件格式非法
    """
    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"minute file not found: {path}")

    _detect_freq_from_suffix(path)

    raw = path.read_bytes()
    if not raw:
        return pd.DataFrame(columns=[
            "date", "time", "open", "high", "low", "close", "amount", "volume"
        ])

    if len(raw) % _MINUTE_RECORD_SIZE != 0:
        raise ValueError(
            f"invalid minute file size: {path}, bytes={len(raw)}, "
            f"not divisible by {_MINUTE_RECORD_SIZE}"
        )

    total = len(raw) // _MINUTE_RECORD_SIZE
    rows: List[Dict[str, Any]] = []

    for i in range(total):
        start = i * _MINUTE_RECORD_SIZE
        rec = raw[start:start + _MINUTE_RECORD_SIZE]
        if len(rec) != _MINUTE_RECORD_SIZE:
            continue

        try:
            date_code, time_code = struct.unpack("<HH", rec[0:4])
            open_f, high_f, low_f, close_f, amount_f = struct.unpack("<fffff", rec[4:24])
            volume_i = struct.unpack("<I", rec[24:28])[0]
            # reserved = struct.unpack("<I", rec[28:32])[0]
        except Exception as e:
            raise ValueError(f"failed to parse minute record idx={i} file={path}: {e}") from e

        date_int = _decode_date_code(date_code)
        time_text = _decode_time_code(time_code)

        if date_int is None:
            raise ValueError(f"invalid minute trade date code idx={i} code={date_code} file={path}")
        if time_text is None:
            raise ValueError(f"invalid minute trade time code idx={i} code={time_code} file={path}")

        rows.append({
            "date": date_int,
            "time": time_text,
            "open": float(open_f),
            "high": float(high_f),
            "low": float(low_f),
            "close": float(close_f),
            "amount": float(amount_f),
            "volume": float(int(volume_i)),
        })

    if not rows:
        return pd.DataFrame(columns=[
            "date", "time", "open", "high", "low", "close", "amount", "volume"
        ])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["date", "time"], keep="last").sort_values(["date", "time"]).reset_index(drop=True)

    _LOG.info("[TDX][MINUTE] parsed rows=%s file=%s", len(df), str(path))
    return df
