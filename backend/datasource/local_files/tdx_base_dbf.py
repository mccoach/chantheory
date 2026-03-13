# backend/datasource/local_files/tdx_base_dbf.py
# ==============================
# TDX 本地 base.dbf 文件解析器
#
# 职责：
#   - 解析 hq_cache/base.dbf
#   - 当前输出 symbol_index / profile 可复用的基础补充字段
#
# 当前字段：
#   - symbol
#   - market
#   - listing_date
#
# 明确不做：
#   - 不与 tnf 合并
#   - 不做业务分类
#   - 不写 DB
# ==============================

from __future__ import annotations

import asyncio
import struct
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd

from backend.settings import settings
from backend.utils.logger import get_logger

_LOG = get_logger("local_files.tdx_base_dbf")


def _hq_cache_dir() -> Path:
    return Path(settings.tdx_hq_cache_dir).resolve()


def _base_dbf_file_path() -> Path:
    return _hq_cache_dir() / "base.dbf"


def _parse_dbf_header(dbf_bytes: bytes) -> Tuple[int, int, int]:
    if len(dbf_bytes) < 32:
        raise ValueError("invalid dbf: header too short")

    record_count = struct.unpack("<I", dbf_bytes[4:8])[0]
    header_len = struct.unpack("<H", dbf_bytes[8:10])[0]
    record_len = struct.unpack("<H", dbf_bytes[10:12])[0]
    return int(record_count), int(header_len), int(record_len)


def _parse_dbf_fields(dbf_bytes: bytes, header_len: int) -> List[Dict[str, Any]]:
    fields: List[Dict[str, Any]] = []
    pos = 32
    while pos + 32 <= header_len:
        desc = dbf_bytes[pos:pos + 32]
        if not desc:
            break
        if desc[0] == 0x0D:
            break

        raw_name = desc[0:11]
        name = raw_name.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
        field_type = chr(desc[11])
        length = desc[16]
        decimal = desc[17]

        fields.append({
            "name": name,
            "type": field_type,
            "length": int(length),
            "decimal": int(decimal),
        })
        pos += 32

    return fields


def _dbf_market_to_text(val: Any) -> Optional[str]:
    s = str(val or "").strip()
    if s == "0":
        return "SZ"
    if s == "1":
        return "SH"
    if s == "2":
        return "BJ"
    return None


def _normalize_dbf_listing_date_text(listing_raw: str) -> Optional[str]:
    s = str(listing_raw or "").strip()
    if not s:
        return None
    if s.isdigit() and len(s) == 8:
        return s
    return None


def load_base_dbf_df_sync() -> pd.DataFrame:
    path = _base_dbf_file_path()
    if not path.exists():
        raise FileNotFoundError(f"base.dbf not found: {path}")

    raw = path.read_bytes()
    record_count, header_len, record_len = _parse_dbf_header(raw)
    fields = _parse_dbf_fields(raw, header_len=header_len)

    if not fields:
        return pd.DataFrame(columns=["symbol", "market", "listing_date"])

    field_names = [f["name"] for f in fields]

    required = {"SC", "GPDM", "SSDATE"}
    if not required.issubset(set(field_names)):
        raise ValueError(
            f"base.dbf missing required fields: {sorted(required - set(field_names))}"
        )

    rows: List[Dict[str, Any]] = []
    offset_data = header_len

    for i in range(record_count):
        start = offset_data + i * record_len
        end = start + record_len
        rec = raw[start:end]
        if len(rec) < record_len:
            continue

        if rec[0:1] == b"*":
            continue

        pos = 1
        row: Dict[str, Any] = {}
        for f in fields:
            length = f["length"]
            chunk = rec[pos:pos + length]
            pos += length

            text = chunk.decode("gbk", errors="ignore").strip()
            row[f["name"]] = text

        market = _dbf_market_to_text(row.get("SC"))
        symbol = str(row.get("GPDM") or "").strip()
        listing_raw = str(row.get("SSDATE") or "").strip()

        if not symbol or not market:
            continue

        listing_date = _normalize_dbf_listing_date_text(listing_raw)

        rows.append({
            "symbol": symbol,
            "market": market,
            "listing_date": listing_date,
        })

    if not rows:
        return pd.DataFrame(columns=["symbol", "market", "listing_date"])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["symbol", "market"], keep="last").reset_index(drop=True)

    if "listing_date" in df.columns:
        df["listing_date"] = df["listing_date"].astype("object")

    _LOG.info(
        "[TDX][BASE_DBF] parsed rows=%s file=%s",
        len(df),
        str(path),
    )
    return df


async def load_base_dbf_df() -> pd.DataFrame:
    """
    异步包装：在线程中解析 base.dbf
    """
    return await asyncio.to_thread(load_base_dbf_df_sync)
