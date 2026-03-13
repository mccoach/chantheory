# backend/datasource/local_files/tdx_tnf.py
# ==============================
# TDX 本地 .tnf 文件解析器
#
# 职责：
#   - 解析 hq_cache/shs.tnf / szs.tnf / bjs.tnf
#   - 返回统一原始 DataFrame
#
# 明确不做：
#   - 不解析 base.dbf
#   - 不做 listing_date 合并
#   - 不做业务分类
#   - 不写 DB
# ==============================

from __future__ import annotations

import struct
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd

from backend.settings import settings
from backend.utils.logger import get_logger

_LOG = get_logger("local_files.tdx_tnf")

_TNF_RECORD_SIZE = 360
_TNF_HEADER_SIZE = 50


def _hq_cache_dir() -> Path:
    return Path(settings.tdx_hq_cache_dir).resolve()


def _tnf_file_path(market: str) -> Path:
    m = str(market or "").strip().upper()
    if m == "SH":
        return _hq_cache_dir() / "shs.tnf"
    if m == "SZ":
        return _hq_cache_dir() / "szs.tnf"
    if m == "BJ":
        return _hq_cache_dir() / "bjs.tnf"
    raise ValueError(f"unsupported market for tnf: {market}")


def _decode_ascii_field(raw: bytes) -> str:
    try:
        return raw.decode("ascii", errors="ignore").strip("\x00 ").strip()
    except Exception:
        return ""


def _decode_gbk_field(raw: bytes) -> str:
    try:
        return raw.decode("gbk", errors="ignore").strip("\x00 ").strip()
    except Exception:
        return ""


def _market_from_market_id(market_id: int) -> Optional[str]:
    if int(market_id) == 0:
        return "SZ"
    if int(market_id) == 1:
        return "SH"
    if int(market_id) == 2:
        return "BJ"
    return None


def _parse_tnf_record(buf: bytes) -> Optional[Dict[str, Any]]:
    if not buf or len(buf) < _TNF_RECORD_SIZE:
        return None

    symbol = _decode_ascii_field(buf[0:20])
    name = _decode_gbk_field(buf[31:63])

    if not symbol:
        return None

    try:
        coarse_type = struct.unpack("<I", buf[76:80])[0]
    except Exception:
        coarse_type = None

    try:
        face_value = struct.unpack("<f", buf[78:82])[0]
    except Exception:
        face_value = None

    try:
        prev_close = struct.unpack("<f", buf[276:280])[0]
    except Exception:
        prev_close = None

    try:
        market_id = struct.unpack("<H", buf[280:282])[0]
    except Exception:
        market_id = None

    market = _market_from_market_id(market_id) if market_id is not None else None
    pinyin = _decode_ascii_field(buf[329:349])

    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "tdx_coarse_type": int(coarse_type) if coarse_type is not None else None,
        "face_value": float(face_value) if face_value is not None else None,
        "prev_close": float(prev_close) if prev_close is not None else None,
        "market_id": int(market_id) if market_id is not None else None,
        "pinyin": pinyin or None,
    }


def load_tnf_df(market: str) -> pd.DataFrame:
    """
    同步解析指定市场的 tnf 文件，返回统一原始 DataFrame。

    输出字段：
      - symbol
      - name
      - market
      - tdx_coarse_type
      - face_value
      - prev_close
      - market_id
      - pinyin
    """
    path = _tnf_file_path(market)
    if not path.exists():
        raise FileNotFoundError(f"tnf file not found: {path}")

    raw = path.read_bytes()
    if len(raw) <= _TNF_HEADER_SIZE:
        return pd.DataFrame()

    payload = raw[_TNF_HEADER_SIZE:]
    total = len(payload) // _TNF_RECORD_SIZE

    rows: List[Dict[str, Any]] = []
    market_upper = str(market).strip().upper()

    for i in range(total):
        start = i * _TNF_RECORD_SIZE
        rec = payload[start:start + _TNF_RECORD_SIZE]
        item = _parse_tnf_record(rec)
        if item:
            # 以文件语义为准，强制覆盖 market
            item["market"] = market_upper
            rows.append(item)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["symbol", "market"], keep="last").reset_index(drop=True)

    _LOG.info(
        "[TDX][TNF] parsed market=%s rows=%s file=%s",
        market_upper,
        len(df),
        str(path),
    )
    return df
