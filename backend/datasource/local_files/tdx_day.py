# backend/datasource/local_files/tdx_day.py
# ==============================
# TDX 本地 .day 文件解析器
#
# 职责：
#   - 解析单个通达信 .day 文件
#   - 返回原始日线 DataFrame
#
# 当前阶段范围：
#   - 只支持 .day
#   - 一条记录 = 一个交易日
#   - 不做业务标准化
#   - 不做写库
#   - 不做路径扫描
#
# 输出原始字段：
#   - date          : YYYYMMDD 整数
#   - open          : float（元）
#   - high          : float（元）
#   - low           : float（元）
#   - close         : float（元）
#   - amount        : float（元）
#   - volume        : float（股）
#
# 通达信 .day 记录格式（32字节）：
#   1. date         4字节 int
#   2. open         4字节 int，价格 * 100
#   3. high         4字节 int，价格 * 100
#   4. low          4字节 int，价格 * 100
#   5. close        4字节 int，价格 * 100
#   6. amount       4字节 float，成交额
#   7. volume       4字节 int，成交量（股）
#   8. reserved     4字节 int，保留
# ==============================

from __future__ import annotations

import struct
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from backend.utils.logger import get_logger

_LOG = get_logger("local_files.tdx_day")

_DAY_RECORD_SIZE = 32


def _safe_price_from_int(value: Any) -> float:
    try:
        return float(int(value)) / 100.0
    except Exception:
        return 0.0


def load_tdx_day_df(file_path: Path | str) -> pd.DataFrame:
    """
    解析单个 .day 文件并返回原始日线 DataFrame。

    Args:
        file_path: .day 文件路径

    Returns:
        DataFrame(columns=[
            'date', 'open', 'high', 'low', 'close', 'amount', 'volume'
        ])

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件格式非法
    """
    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f".day file not found: {path}")

    raw = path.read_bytes()
    if not raw:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "amount", "volume"])

    if len(raw) % _DAY_RECORD_SIZE != 0:
        raise ValueError(
            f"invalid .day file size: {path}, bytes={len(raw)}, "
            f"not divisible by {_DAY_RECORD_SIZE}"
        )

    total = len(raw) // _DAY_RECORD_SIZE
    rows: List[Dict[str, Any]] = []

    for i in range(total):
        start = i * _DAY_RECORD_SIZE
        rec = raw[start:start + _DAY_RECORD_SIZE]
        if len(rec) != _DAY_RECORD_SIZE:
            continue

        try:
            date_val = struct.unpack("<I", rec[0:4])[0]
            open_i = struct.unpack("<I", rec[4:8])[0]
            high_i = struct.unpack("<I", rec[8:12])[0]
            low_i = struct.unpack("<I", rec[12:16])[0]
            close_i = struct.unpack("<I", rec[16:20])[0]
            amount_f = struct.unpack("<f", rec[20:24])[0]
            volume_i = struct.unpack("<I", rec[24:28])[0]
        except Exception as e:
            raise ValueError(f"failed to parse .day record idx={i} file={path}: {e}") from e

        date_int = int(date_val)
        if not (19000101 <= date_int <= 21001231):
            # 日期明显非法，直接视为文件损坏
            raise ValueError(f"invalid trade date in .day file: idx={i} date={date_int} file={path}")

        rows.append({
            "date": date_int,
            "open": _safe_price_from_int(open_i),
            "high": _safe_price_from_int(high_i),
            "low": _safe_price_from_int(low_i),
            "close": _safe_price_from_int(close_i),
            "amount": float(amount_f),
            "volume": float(int(volume_i)),
        })

    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "amount", "volume"])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)

    _LOG.info("[TDX][DAY] parsed rows=%s file=%s", len(df), str(path))
    return df
